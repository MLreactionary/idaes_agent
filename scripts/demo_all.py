import json
import sys
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def close_enough(actual, expected, tolerance_abs=1e-6):
    return abs(float(actual) - float(expected)) <= float(tolerance_abs)


def evaluate_numeric(parsed: dict, field: str, expected: float, tolerance_abs: float = 1e-6):
    actual = parsed.get(field)

    if actual is None:
        return False, f"Missing field {field}"

    if not close_enough(actual, expected, tolerance_abs):
        return False, f"Expected {field}={expected}, got {actual}"

    return True, f"{field}={actual}"


def run_standard_case(case: dict) -> dict:
    print("")
    print("=" * 100)
    print(f"DEMO CASE: {case['id']}")
    print("=" * 100)
    print(case["prompt"])

    result = run_problem(
        prompt=case["prompt"],
        planner="llm",
        explain=False,
        repair=False,
        inject_bug=False,
        max_repair_attempts=0
    )

    run_dir = Path(result["run_dir"])
    parsed = load_json(run_dir / "parsed_result.json")

    checks = []

    checks.append({
        "name": "verified",
        "passed": result.get("verified") is True,
        "message": f"verified={result.get('verified')}"
    })

    checks.append({
        "name": "problem_type",
        "passed": parsed.get("problem_type") == case["expected_problem_type"],
        "message": f"problem_type={parsed.get('problem_type')}"
    })

    checks.append({
        "name": "mode",
        "passed": parsed.get("mode") == case["expected_mode"],
        "message": f"mode={parsed.get('mode')}"
    })

    for expectation in case.get("numeric_expectations", []):
        passed, message = evaluate_numeric(
            parsed=parsed,
            field=expectation["field"],
            expected=expectation["expected"],
            tolerance_abs=expectation.get("tolerance_abs", 1e-6)
        )

        checks.append({
            "name": expectation["field"],
            "passed": passed,
            "message": message
        })

    passed = all(check["passed"] for check in checks)

    summary = {
        "id": case["id"],
        "passed": passed,
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "report_path": result["report_path"],
        "checks": checks
    }

    print("")
    print("CASE RESULT")
    print(json.dumps(summary, indent=2, sort_keys=True))

    return summary


def run_repair_case() -> dict:
    print("")
    print("=" * 100)
    print("DEMO CASE: controlled_repair_smoke")
    print("=" * 100)

    prompt = "Heat water from 300 K to 350 K at 1 bar and report heat duty."
    print(prompt)

    result = run_problem(
        prompt=prompt,
        planner="llm",
        explain=False,
        repair=True,
        inject_bug=True,
        max_repair_attempts=1
    )

    run_dir = Path(result["run_dir"])
    trace = load_json(run_dir / "repair_attempt_1_trace.json")
    report_text = (run_dir / "report.md").read_text(encoding="utf-8")

    allowed_patch_strategies = {
        "minimal_import_patch_from_llm_candidate",
        "minimal_import_patch_deterministic",
    }

    checks = [
        {
            "name": "verified",
            "passed": result.get("verified") is True,
            "message": f"verified={result.get('verified')}"
        },
        {
            "name": "repair_attempts_used",
            "passed": result.get("repair_attempts_used") == 1,
            "message": f"repair_attempts_used={result.get('repair_attempts_used')}"
        },
        {
            "name": "patch_strategy",
            "passed": trace.get("patch_strategy") in allowed_patch_strategies,
            "message": f"patch_strategy={trace.get('patch_strategy')}"
        },
        {
            "name": "report_has_repair_history",
            "passed": "## Repair History" in report_text,
            "message": "repair history present" if "## Repair History" in report_text else "repair history missing"
        }
    ]

    passed = all(check["passed"] for check in checks)

    summary = {
        "id": "controlled_repair_smoke",
        "passed": passed,
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "report_path": result["report_path"],
        "checks": checks
    }

    print("")
    print("CASE RESULT")
    print(json.dumps(summary, indent=2, sort_keys=True))

    return summary


def write_demo_reports(demo_result: dict):
    output_dir = PROJECT_ROOT / "outputs" / "demos"
    output_dir.mkdir(parents=True, exist_ok=True)

    demo_id = demo_result["demo_id"]

    json_path = output_dir / f"{demo_id}.json"
    md_path = output_dir / f"{demo_id}.md"

    json_path.write_text(
        json.dumps(demo_result, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    lines = []
    lines.append(f"# Demo Report: {demo_id}")
    lines.append("")
    lines.append(f"- Passed: `{demo_result['passed']}`")
    lines.append(f"- Total cases: `{demo_result['total_cases']}`")
    lines.append(f"- Passed cases: `{demo_result['passed_cases']}`")
    lines.append(f"- Failed cases: `{demo_result['failed_cases']}`")
    lines.append("")

    lines.append("## Cases")
    lines.append("")

    for case in demo_result["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        lines.append(f"### {case['id']} — {status}")
        lines.append("")
        lines.append(f"- Run ID: `{case['run_id']}`")
        lines.append(f"- Report: `{case['report_path']}`")
        lines.append("")
        lines.append("Checks:")
        for check in case["checks"]:
            check_status = "PASS" if check["passed"] else "FAIL"
            lines.append(f"- `{check['name']}`: {check_status} — {check['message']}")
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return json_path, md_path


def main():
    demo_id = "demo_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    cases = [
        {
            "id": "heater_heat_duty",
            "prompt": "Heat water from 300 K to 350 K at 1 bar and report heat duty.",
            "expected_problem_type": "heater_energy_balance",
            "expected_mode": "calculate_heat_duty",
            "numeric_expectations": [
                {
                    "field": "heat_duty_w",
                    "expected": 209200.0
                }
            ]
        },
        {
            "id": "heater_outlet_temperature",
            "prompt": "Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?",
            "expected_problem_type": "heater_energy_balance",
            "expected_mode": "calculate_outlet_temperature",
            "numeric_expectations": [
                {
                    "field": "temperature_out_k",
                    "expected": 323.90057361376677
                }
            ]
        },
        {
            "id": "heater_mass_flow",
            "prompt": "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?",
            "expected_problem_type": "heater_energy_balance",
            "expected_mode": "calculate_mass_flow",
            "numeric_expectations": [
                {
                    "field": "mass_flow_kg_s",
                    "expected": 0.4345558838866678
                }
            ]
        },
        {
            "id": "adiabatic_mixer",
            "prompt": "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?",
            "expected_problem_type": "adiabatic_mixer",
            "expected_mode": "calculate_outlet_temperature",
            "numeric_expectations": [
                {
                    "field": "temperature_out_k",
                    "expected": 340.0
                }
            ]
        },
        {
            "id": "blend_cost_optimization",
            "prompt": (
                "Optimize a blend of 100 kg product using source A cost 2 $/kg impurity 1% "
                "and source B cost 1 $/kg impurity 5%, with final impurity limit 3%. "
                "What is the minimum cost blend?"
            ),
            "expected_problem_type": "blend_cost_optimization",
            "expected_mode": "minimize_cost",
            "numeric_expectations": [
                {
                    "field": "source1_mass_kg",
                    "expected": 50.0
                },
                {
                    "field": "source2_mass_kg",
                    "expected": 50.0
                },
                {
                    "field": "total_cost",
                    "expected": 150.0
                },
                {
                    "field": "final_impurity_fraction",
                    "expected": 0.03
                }
            ]
        },
        {
            "id": "general_blend_cost_optimization",
            "prompt": (
                "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, "
                "source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. "
                "Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost."
            ),
            "expected_problem_type": "general_blend_cost_optimization",
            "expected_mode": "minimize_cost",
            "numeric_expectations": [
                {
                    "field": "number_of_sources",
                    "expected": 3
                },
                {
                    "field": "total_mass_kg",
                    "expected": 100.0
                },
                {
                    "field": "total_cost",
                    "expected": 140.0
                },
                {
                    "field": "maximum_quality_violation_fraction",
                    "expected": 0.0
                }
            ]
        },
    ]

    case_results = []

    for case in cases:
        case_results.append(run_standard_case(case))

    case_results.append(run_repair_case())

    passed_cases = sum(1 for case in case_results if case["passed"])
    total_cases = len(case_results)
    failed_cases = total_cases - passed_cases

    demo_result = {
        "demo_id": demo_id,
        "passed": failed_cases == 0,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "cases": case_results
    }

    json_path, md_path = write_demo_reports(demo_result)

    print("")
    print("=" * 100)
    print("DEMO COMPLETE")
    print("=" * 100)
    print(
        json.dumps(
            {
                "demo_id": demo_id,
                "passed": demo_result["passed"],
                "total_cases": total_cases,
                "passed_cases": passed_cases,
                "failed_cases": failed_cases,
                "json_path": str(json_path),
                "markdown_path": str(md_path)
            },
            indent=2,
            sort_keys=True
        )
    )

    if failed_cases > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
