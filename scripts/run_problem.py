import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.planner import plan_problem as regex_plan_problem
from app.llm_planner import plan_problem_with_llm
from app.mixer_planner import is_mixer_prompt, plan_mixer_problem
from app.splitter_planner import is_splitter_prompt, plan_splitter_problem
from app.codegen import write_generated_model
from app.executor import execute_model
from app.parser import parse_execution_result
from app.verifier import write_verification
from app.explainer import generate_engineering_explanation
from app.repair import repair_generated_model
from app.report import generate_report
from app.repair_report import append_repair_history_to_report
from app.store import upsert_run, record_run_from_files


def make_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_id = uuid.uuid4().hex[:8]
    return f"run_{timestamp}_{short_id}"


def choose_planner(prompt: str, planner: str, run_dir: Path) -> dict:
    if is_splitter_prompt(prompt):
        return plan_splitter_problem(prompt, trace_dir=run_dir)

    if is_mixer_prompt(prompt):
        return plan_mixer_problem(prompt, trace_dir=run_dir)

    if planner == "regex":
        spec = regex_plan_problem(prompt)

        planner_trace = {
            "planner": "regex",
            "prompt": prompt,
            "extracted_json": spec,
            "note": "Temporary deterministic regex planner. No LLM call was made."
        }

        (run_dir / "planner_trace.json").write_text(
            json.dumps(planner_trace, indent=2, sort_keys=True),
            encoding="utf-8"
        )

        return spec

    if planner == "llm":
        return plan_problem_with_llm(prompt, trace_dir=run_dir)

    raise ValueError(f"Unknown planner: {planner}")


def inject_controlled_bug(model_path: Path, run_dir: Path, bug_type: str = "bad_import") -> None:
    """
    Intentionally break generated_model.py for controlled repair testing.

    This changes:
        import pyomo.environ as pyo

    into:
        import pyomox.environ as pyo

    That creates a clean execution failure for the repair loop.
    """
    model_path = Path(model_path)
    code = model_path.read_text(encoding="utf-8")

    if bug_type == "bad_import":
        target = "import pyomo.environ as pyo"
        replacement = "import pyomox.environ as pyo"
        description = "Changed pyomo import to pyomox import to force execution failure."

    elif bug_type == "splitter_wrong_split_key":
        target = 'spec["outlet1_split_fraction"]'
        replacement = 'spec["outlet1_split_fraction_WRONG"]'
        description = "Changed splitter structured-spec key to force a family-specific execution failure."

    else:
        raise RuntimeError(f"Unknown controlled bug type: {bug_type}")

    if target not in code:
        raise RuntimeError(
            f"Could not inject bug_type={bug_type} because target was not found: {target}"
        )

    broken_code = code.replace(target, replacement, 1)
    model_path.write_text(broken_code, encoding="utf-8")

    bug_record = {
        "bug_type": bug_type,
        "description": description,
        "target": target,
        "replacement": replacement
    }

    (run_dir / "injected_bug.json").write_text(
        json.dumps(bug_record, indent=2, sort_keys=True),
        encoding="utf-8"
    )


def execute_with_optional_repair(
    run_id: str,
    run_dir: Path,
    model_path: Path,
    original_prompt: str,
    repair: bool,
    max_repair_attempts: int
):
    execution_result = execute_model(
        model_path=model_path,
        run_dir=run_dir,
        timeout_seconds=30
    )

    repair_attempts_used = 0

    while (
        repair
        and execution_result.return_code != 0
        and repair_attempts_used < max_repair_attempts
    ):
        repair_attempts_used += 1

        upsert_run(
            run_id=run_id,
            status=f"repair_attempt_{repair_attempts_used}",
            run_dir=run_dir,
            raw_output_path=execution_result.raw_output_path
        )

        repair_generated_model(
            run_id=run_id,
            run_dir=run_dir,
            original_prompt=original_prompt,
            execution_result=execution_result,
            attempt_index=repair_attempts_used
        )

        execution_result = execute_model(
            model_path=model_path,
            run_dir=run_dir,
            timeout_seconds=30
        )

    if execution_result.return_code != 0:
        raise RuntimeError(
            f"generated_model.py failed after {repair_attempts_used} repair attempts. "
            f"return_code={execution_result.return_code}. "
            f"See raw_output.txt in {run_dir}"
        )

    return execution_result, repair_attempts_used


def run_problem(
    prompt: str,
    planner: str = "llm",
    explain: bool = False,
    repair: bool = False,
    inject_bug: bool = False,
    max_repair_attempts: int = 1,
    inject_bug_type: str = "bad_import",
    backend: str | None = None
) -> dict:
    run_id = make_run_id()
    run_dir = PROJECT_ROOT / "outputs" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    input_path = run_dir / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "original_prompt": prompt,
                "planner": planner,
                "explain": explain,
                "repair": repair,
                "inject_bug": inject_bug,
                "max_repair_attempts": max_repair_attempts,
                "inject_bug_type": inject_bug_type,
                "backend": backend
            },
            indent=2,
            sort_keys=True
        ),
        encoding="utf-8"
    )

    try:
        upsert_run(
            run_id=run_id,
            status="started",
            original_prompt=prompt,
            run_dir=run_dir
        )

        spec = choose_planner(prompt, planner=planner, run_dir=run_dir)

        model_path = write_generated_model(
            spec,
            run_dir,
            backend_override=backend
        )

        if inject_bug:
            inject_controlled_bug(
                model_path=model_path,
                run_dir=run_dir,
                bug_type=inject_bug_type
            )

        upsert_run(
            run_id=run_id,
            status="generated",
            problem_type=spec.get("problem_type"),
            mode=spec.get("mode"),
            generated_code_path=model_path,
            structured_spec_path=run_dir / "structured_spec.json",
            run_dir=run_dir
        )

        execution_result, repair_attempts_used = execute_with_optional_repair(
            run_id=run_id,
            run_dir=run_dir,
            model_path=model_path,
            original_prompt=prompt,
            repair=repair,
            max_repair_attempts=max_repair_attempts
        )

        upsert_run(
            run_id=run_id,
            status="executed",
            raw_output_path=execution_result.raw_output_path,
            run_dir=run_dir
        )

        parsed_result_path = parse_execution_result(
            stdout=execution_result.stdout,
            run_dir=run_dir
        )

        upsert_run(
            run_id=run_id,
            status="parsed",
            parsed_result_path=parsed_result_path,
            run_dir=run_dir
        )

        verification_path = write_verification(
            parsed_result_path=parsed_result_path,
            structured_spec_path=run_dir / "structured_spec.json",
            run_dir=run_dir
        )

        verification = json.loads(
            verification_path.read_text(encoding="utf-8")
        )

        upsert_run(
            run_id=run_id,
            status="verified" if verification["verified"] else "failed_verification",
            verified=verification["verified"],
            num_failures=verification["num_failures"],
            verification_path=verification_path,
            run_dir=run_dir
        )

        explanation_path = None
        if explain and verification["verified"]:
            explanation_path = generate_engineering_explanation(
                run_dir=run_dir,
                original_prompt=prompt
            )

        report_path = generate_report(
            run_id=run_id,
            original_prompt=prompt,
            run_dir=run_dir
        )

        append_repair_history_to_report(
            run_dir=run_dir,
            report_path=report_path
        )

        record_run_from_files(
            run_id=run_id,
            original_prompt=prompt,
            run_dir=run_dir
        )

        result = {
            "run_id": run_id,
            "planner": planner,
            "explain": explain,
            "repair": repair,
            "inject_bug": inject_bug,
            "inject_bug_type": inject_bug_type,
            "backend": backend,
            "repair_attempts_used": repair_attempts_used,
            "status": "verified" if verification["verified"] else "failed_verification",
            "verified": verification["verified"],
            "num_failures": verification["num_failures"],
            "run_dir": str(run_dir),
            "report_path": str(report_path)
        }

        if explanation_path is not None:
            result["explanation_path"] = str(explanation_path)

        return result

    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"

        error_path = run_dir / "error.json"
        error_path.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "planner": planner,
                    "explain": explain,
                    "repair": repair,
                    "inject_bug": inject_bug,
                    "inject_bug_type": inject_bug_type,
                    "backend": backend,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)
                },
                indent=2,
                sort_keys=True
            ),
            encoding="utf-8"
        )

        upsert_run(
            run_id=run_id,
            status="error",
            original_prompt=prompt,
            run_dir=run_dir,
            error_message=error_message
        )

        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--planner",
        choices=["llm", "regex"],
        default="llm",
        help="Planner to use. Default: llm"
    )
    parser.add_argument(
        "--backend",
        choices=["pyomo", "idaes"],
        default=None,
        help="Optional backend override. Example: --backend idaes"
    )
    parser.add_argument(
        "--explain",
        action="store_true",
        help="Generate a short LLM engineering explanation after deterministic verification passes."
    )
    parser.add_argument(
        "--repair",
        action="store_true",
        help="Enable LLM repair if generated_model.py execution fails."
    )
    parser.add_argument(
        "--inject-bug",
        action="store_true",
        help="Inject a controlled bug into generated_model.py for repair testing."
    )
    parser.add_argument(
        "--max-repair-attempts",
        type=int,
        default=1,
        help="Maximum number of repair attempts. Default: 1."
    )
    parser.add_argument(
        "--inject-bug-type",
        choices=["bad_import", "splitter_wrong_split_key"],
        default="bad_import",
        help="Controlled bug type to inject when --inject-bug is used."
    )
    parser.add_argument("prompt", nargs="+")

    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    result = run_problem(
        prompt,
        planner=args.planner,
        explain=args.explain,
        repair=args.repair,
        inject_bug=args.inject_bug,
        max_repair_attempts=args.max_repair_attempts,
        inject_bug_type=args.inject_bug_type,
        backend=args.backend
    )

    print("")
    print("Run complete")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
