
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
from app.scaffold_guided_codegen import generate_scaffold_guided_model_code, repair_generated_model_code_after_runtime


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


def write_llm_generated_model(run_dir: Path, prompt: str, spec: dict, solver_name: str) -> Path:
    generated_path = run_dir / "generated_model.py"

    code = generate_scaffold_guided_model_code(
        prompt=prompt,
        spec=spec,
        solver_name=solver_name,
        trace_dir=run_dir,
    )

    generated_path.write_text(code, encoding="utf-8")
    return generated_path


def normalize_result_with_spec(spec: dict, result: dict) -> dict:
    if not isinstance(result, dict):
        return result

    source_lookup = {
        source["name"]: source
        for source in spec.get("sources", [])
    }

    product_mass = float(spec.get("product_mass_kg", 0.0))
    raw_source_results = result.get("source_results", [])
    normalized_sources = []

    if isinstance(raw_source_results, dict):
        items = raw_source_results.items()
        for source_name, value in items:
            if isinstance(value, dict):
                mass_kg = float(value.get("mass_kg", value.get("mass", 0.0)))
            else:
                mass_kg = float(value)

            source = source_lookup.get(source_name, {})
            cost_per_kg = float(source.get("cost_per_kg", 0.0))

            normalized_sources.append(
                {
                    "name": source_name,
                    "mass_kg": mass_kg,
                    "cost_per_kg": cost_per_kg,
                    "cost": mass_kg * cost_per_kg,
                    "qualities": source.get("qualities", {}),
                    "min_required_kg": source.get("min_required_kg"),
                    "max_available_kg": source.get("max_available_kg"),
                }
            )

    elif isinstance(raw_source_results, list):
        for item in raw_source_results:
            if not isinstance(item, dict):
                continue

            source_name = item.get("name")
            if source_name is None:
                continue

            mass_kg = float(item.get("mass_kg", item.get("mass", 0.0)))
            source = source_lookup.get(source_name, {})
            cost_per_kg = float(item.get("cost_per_kg", source.get("cost_per_kg", 0.0)))

            enriched = dict(item)
            enriched["name"] = source_name
            enriched["mass_kg"] = mass_kg
            enriched["cost_per_kg"] = cost_per_kg
            enriched["cost"] = float(item.get("cost", mass_kg * cost_per_kg))
            enriched["qualities"] = item.get("qualities", source.get("qualities", {}))
            normalized_sources.append(enriched)

    total_mass = sum(source["mass_kg"] for source in normalized_sources)
    total_cost = sum(source["cost"] for source in normalized_sources)

    quality_names = sorted(
        {
            quality_name
            for source in source_lookup.values()
            for quality_name in source.get("qualities", {}).keys()
        }
    )

    quality_results = {}

    if abs(total_mass) > 1e-12:
        for quality_name in quality_names:
            quality_results[quality_name] = sum(
                float(source.get("qualities", {}).get(quality_name, 0.0)) * source["mass_kg"]
                for source in normalized_sources
            ) / total_mass

    lower_bounds = spec.get("quality_lower_bounds", {}) or {}
    upper_bounds = spec.get("quality_upper_bounds", {}) or {}

    quality_lower_slacks = {
        name: quality_results.get(name, 0.0) - float(bound)
        for name, bound in lower_bounds.items()
    }

    quality_upper_slacks = {
        name: float(bound) - quality_results.get(name, 0.0)
        for name, bound in upper_bounds.items()
    }

    result["problem_type"] = spec.get("problem_type", "general_blend_cost_optimization")
    result["backend"] = result.get("backend", "llm_generated_pyomo")
    result["source_results"] = normalized_sources
    result["total_blended_mass_kg"] = total_mass
    result["total_cost"] = total_cost
    result["mass_balance_residual_kg"] = product_mass - total_mass
    result["quality_results"] = quality_results
    result["quality_lower_bounds"] = lower_bounds
    result["quality_upper_bounds"] = upper_bounds
    result["quality_lower_slacks"] = quality_lower_slacks
    result["quality_upper_slacks"] = quality_upper_slacks
    result["maximum_quality_lower_violation"] = max([max(-slack, 0.0) for slack in quality_lower_slacks.values()] or [0.0])
    result["maximum_quality_upper_violation"] = max([max(-slack, 0.0) for slack in quality_upper_slacks.values()] or [0.0])

    if "solver_status" in result:
        result["solver_status"] = str(result["solver_status"])

    if "termination_condition" in result:
        result["termination_condition"] = str(result["termination_condition"])

    return result


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

        source_results = result.get("source_results", [])

        if isinstance(source_results, dict):
            normalized_sources = []
            for source_name, value in source_results.items():
                if isinstance(value, dict):
                    item = {"name": source_name}
                    item.update(value)
                else:
                    item = {"name": source_name, "mass_kg": value}
                normalized_sources.append(item)
        else:
            normalized_sources = source_results

        for source in normalized_sources:
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


def run_domain_agent(prompt: str, solver_name: str = "glpk", codegen_mode: str = "wrapper") -> dict:
    run_dir = make_run_dir()

    (run_dir / "input_prompt.txt").write_text(prompt + "\n", encoding="utf-8")

    spec = extract_general_blend_spec(prompt, trace_dir=run_dir)

    (run_dir / "structured_spec.json").write_text(
        json.dumps(spec, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if codegen_mode == "llm":
        generated_model_path = write_llm_generated_model(run_dir, prompt, spec, solver_name)
    elif codegen_mode == "wrapper":
        generated_model_path = write_generated_model(run_dir, spec, solver_name)
    else:
        raise ValueError("Unsupported codegen mode: " + codegen_mode)

    completed = subprocess.run(
        [sys.executable, str(generated_model_path)],
        cwd=str(PROJECT_ROOT),
        text=True,
        capture_output=True,
        check=False,
    )

    raw_output = completed.stdout + completed.stderr
    (run_dir / "raw_output.txt").write_text(raw_output, encoding="utf-8")

    if completed.returncode != 0 and codegen_mode == "llm":
        broken_code = generated_model_path.read_text(encoding="utf-8")
        repaired_code = repair_generated_model_code_after_runtime(
            prompt=prompt,
            spec=spec,
            solver_name=solver_name,
            broken_code=broken_code,
            raw_output=raw_output,
        )

        repaired_model_path = run_dir / "generated_model_runtime_repair.py"
        repaired_model_path.write_text(repaired_code, encoding="utf-8")
        generated_model_path = repaired_model_path

        completed = subprocess.run(
            [sys.executable, str(generated_model_path)],
            cwd=str(PROJECT_ROOT),
            text=True,
            capture_output=True,
            check=False,
        )

        raw_output = completed.stdout + completed.stderr
        (run_dir / "raw_output_after_runtime_repair.txt").write_text(raw_output, encoding="utf-8")

    if completed.returncode != 0:
        raise RuntimeError(
            f"Generated model failed with return code {completed.returncode}. See {run_dir / 'raw_output.txt'} and runtime repair output if present."
        )

    result = normalize_result_with_spec(spec, extract_result_json(raw_output))

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
    parser.add_argument("--codegen", choices=["wrapper", "llm"], default="wrapper")

    args = parser.parse_args()

    result = run_domain_agent(args.prompt, solver_name=args.solver, codegen_mode=args.codegen)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
