
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.llm_spec_extractor import extract_general_blend_spec


def make_run_dir() -> Path:
    run_id = datetime.now().strftime("blend_domain_%Y%m%d_%H%M%S_") + uuid4().hex[:8]
    run_dir = PROJECT_ROOT / "outputs" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def extract_result_json(raw_output: str) -> dict:
    start_marker = "RESULT_JSON_START"
    end_marker = "RESULT_JSON_END"

    start = raw_output.find(start_marker)
    end = raw_output.find(end_marker)

    if start < 0 or end < 0:
        raise RuntimeError("Generated model did not emit RESULT_JSON markers.")

    payload = raw_output[start + len(start_marker):end].strip()
    return json.loads(payload)


def write_generated_model(run_dir: Path, spec: dict, solver_name: str) -> Path:
    generated_path = run_dir / "generated_model.py"

    code = """from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.general_blend_domain_solver import solve_general_blend_spec

SPEC = __SPEC_JSON__
SOLVER_NAME = __SOLVER_NAME_JSON__

result = solve_general_blend_spec(SPEC, solver_name=SOLVER_NAME)

print(\"RESULT_JSON_START\")
print(json.dumps(result, indent=2, sort_keys=True))
print(\"RESULT_JSON_END\")
"""

    code = code.replace("__SPEC_JSON__", json.dumps(spec, indent=2, sort_keys=True))
    code = code.replace("__SOLVER_NAME_JSON__", json.dumps(solver_name))

    generated_path.write_text(code, encoding="utf-8")
    return generated_path


def write_report(run_dir: Path, prompt: str, spec: dict, result: dict) -> None:
    lines = [
        "# General Blend Domain Agent Report",
        "",
        "## Prompt",
        "",
        prompt,
        "",
        "## Extracted Structured Spec",
        "",
        "```json",
        json.dumps(spec, indent=2, sort_keys=True),
        "```",
        "",
        "## Parsed Result",
        "",
        "```json",
        json.dumps(result, indent=2, sort_keys=True),
        "```",
        "",
    ]

    if result.get("solver_status") == "ok":
        lines.extend(
            [
                "## Summary",
                "",
                f"Total cost: {result.get('total_cost')}",
                f"Total blended mass kg: {result.get('total_blended_mass_kg')}",
                f"Mass balance residual kg: {result.get('mass_balance_residual_kg')}",
                "",
                "## Source Decisions",
                "",
            ]
        )

        for source in result.get("source_results", []):
            lines.append(
                f"- {source.get('name')}: {source.get('mass_kg')} kg, cost {source.get('cost')}"
            )

        lines.extend(["", "## Quality Results", ""])

        for name, value in sorted(result.get("quality_results", {}).items()):
            lines.append(f"- {name}: {value}")

    if result.get("solver_status") == "infeasible":
        lines.extend(["## Infeasibility Diagnosis", ""])

        for reason in result.get("infeasibility_diagnosis", {}).get("reasons", []):
            lines.append(f"- {reason}")

    (run_dir / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_domain_agent(prompt: str, solver_name: str = "glpk") -> dict:
    run_dir = make_run_dir()

    (run_dir / "input_prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    spec = extract_general_blend_spec(prompt, trace_dir=run_dir)

    (run_dir / "structured_spec.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    generated_model_path = write_generated_model(run_dir, spec, solver_name)

    completed = subprocess.run(
        [sys.executable, str(generated_model_path)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    raw_output = completed.stdout + completed.stderr
    (run_dir / "raw_output.txt").write_text(raw_output, encoding="utf-8")

    if completed.returncode != 0:
        raise RuntimeError(
            f"Generated model failed with return code {completed.returncode}. See {run_dir / raw_output.txt}"
        )

    result = extract_result_json(raw_output)

    (run_dir / "parsed_result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    write_report(run_dir, prompt, spec, result)

    return {
        "status": "ok",
        "run_dir": str(run_dir),
        "structured_spec_path": str(run_dir / "structured_spec.json"),
        "generated_model_path": str(generated_model_path),
        "parsed_result_path": str(run_dir / "parsed_result.json"),
        "report_path": str(run_dir / "report.md"),
        "result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--solver", default="glpk")

    args = parser.parse_args()

    result = run_domain_agent(args.prompt, solver_name=args.solver)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
