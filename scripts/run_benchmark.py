import argparse
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


def close_enough(actual, expected, tolerance_abs):
    return abs(float(actual) - float(expected)) <= float(tolerance_abs)


def get_result_value(parsed: dict, field: str):
    if "." not in field:
        return parsed.get(field)

    current = parsed

    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)

    return current


def evaluate_success_case(case: dict, run_result: dict) -> tuple[bool, list[str]]:
    messages = []

    run_dir = Path(run_result["run_dir"])
    parsed_result_path = run_dir / "parsed_result.json"

    if not parsed_result_path.exists():
        return False, [f"Missing parsed_result.json: {parsed_result_path}"]

    parsed = load_json(parsed_result_path)

    if not run_result.get("verified"):
        messages.append("Run was not verified.")

    expected_problem_type = case.get("expected_problem_type")
    if expected_problem_type is not None:
        actual_problem_type = parsed.get("problem_type")
        if actual_problem_type != expected_problem_type:
            messages.append(
                f"Expected problem_type {expected_problem_type}, got {actual_problem_type}."
            )

    expected_mode = case.get("expected_mode")
    if expected_mode is not None:
        actual_mode = parsed.get("mode")
        if actual_mode != expected_mode:
            messages.append(f"Expected mode {expected_mode}, got {actual_mode}.")

    tolerance_abs = case.get("tolerance_abs", 1e-6)

    legacy_numeric_expectations = [
        ("expected_heat_duty_w", "heat_duty_w"),
        ("expected_temperature_out_k", "temperature_out_k"),
        ("expected_mass_flow_kg_s", "mass_flow_kg_s"),
    ]

    for expected_key, result_key in legacy_numeric_expectations:
        if expected_key not in case:
            continue

        expected = case[expected_key]
        actual = parsed.get(result_key)

        if actual is None:
            messages.append(f"Missing result field {result_key}.")
            continue

        if not close_enough(actual, expected, tolerance_abs):
            messages.append(
                f"Expected {result_key}={expected}, got {actual}, tolerance={tolerance_abs}."
            )

    for expectation in case.get("numeric_expectations", []):
        field = expectation["field"]
        expected = expectation["expected"]
        expectation_tolerance = expectation.get("tolerance_abs", tolerance_abs)
        actual = get_result_value(parsed, field)

        if actual is None:
            messages.append(f"Missing result field {field}.")
            continue

        if not close_enough(actual, expected, expectation_tolerance):
            messages.append(
                f"Expected {field}={expected}, got {actual}, tolerance={expectation_tolerance}."
            )

    return len(messages) == 0, messages


def run_case(case: dict, planner: str) -> dict:
    case_id = case["id"]
    prompt = case["prompt"]
    expect_error = case.get("expect_error", False)

    print("-" * 80)
    print(f"Running case: {case_id}")
    print(f"Prompt: {prompt}")

    try:
        run_result = run_problem(
            prompt=prompt,
            planner=planner,
            explain=False,
            repair=False,
            inject_bug=False,
            max_repair_attempts=0
        )

        if expect_error:
            result = {
                "id": case_id,
                "prompt": prompt,
                "outcome": "unexpected_success",
                "passed": False,
                "run_result": run_result,
                "messages": ["Expected an error, but run succeeded."]
            }
        else:
            passed, messages = evaluate_success_case(case, run_result)

            result = {
                "id": case_id,
                "prompt": prompt,
                "outcome": "passed" if passed else "failed",
                "passed": passed,
                "run_result": run_result,
                "messages": messages
            }

    except Exception as exc:
        if expect_error:
            result = {
                "id": case_id,
                "prompt": prompt,
                "outcome": "expected_error",
                "passed": True,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "messages": []
            }
        else:
            result = {
                "id": case_id,
                "prompt": prompt,
                "outcome": "unexpected_error",
                "passed": False,
                "error_type": type(exc).__name__,
                "error_message": str(exc),
                "messages": [str(exc)]
            }

    print(f"Outcome: {result['outcome']}")
    print(f"Case passed: {result['passed']}")

    if result.get("messages"):
        print("Messages:")
        for message in result["messages"]:
            print(f"  - {message}")

    return result


def write_markdown_report(benchmark_result: dict, markdown_path: Path):
    lines = []
    lines.append(f"# Benchmark Report: {benchmark_result['benchmark_id']}")
    lines.append("")
    lines.append(f"- Planner: `{benchmark_result['planner']}`")
    lines.append(f"- Total cases: `{benchmark_result['total_cases']}`")
    lines.append(f"- Passed cases: `{benchmark_result['passed_cases']}`")
    lines.append(f"- Failed cases: `{benchmark_result['failed_cases']}`")
    lines.append("")

    lines.append("## Cases")
    lines.append("")

    for case_result in benchmark_result["case_results"]:
        status = "PASS" if case_result["passed"] else "FAIL"
        lines.append(f"### {case_result['id']} — {status}")
        lines.append("")
        lines.append(f"- Outcome: `{case_result['outcome']}`")
        lines.append(f"- Prompt: {case_result['prompt']}")

        if "run_result" in case_result:
            run_result = case_result["run_result"]
            lines.append(f"- Run ID: `{run_result.get('run_id')}`")
            lines.append(f"- Verified: `{run_result.get('verified')}`")
            lines.append(f"- Report: `{run_result.get('report_path')}`")

        if case_result.get("messages"):
            lines.append("")
            lines.append("Messages:")
            for message in case_result["messages"]:
                lines.append(f"- {message}")

        if case_result.get("error_message"):
            lines.append(f"- Error: `{case_result['error_message']}`")

        lines.append("")

    markdown_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--planner", choices=["llm", "regex"], default="llm")
    parser.add_argument(
        "--benchmark-file",
        default="benchmarks/heater_mvp_prompts.json"
    )

    args = parser.parse_args()

    benchmark_path = PROJECT_ROOT / args.benchmark_file
    cases = load_json(benchmark_path)

    benchmark_id = "benchmark_" + datetime.now().strftime("%Y%m%d_%H%M%S")

    case_results = []

    for case in cases:
        case_results.append(run_case(case, planner=args.planner))

    passed_cases = sum(1 for result in case_results if result["passed"])
    total_cases = len(case_results)
    failed_cases = total_cases - passed_cases

    output_dir = PROJECT_ROOT / "outputs" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"{benchmark_id}.json"
    markdown_path = output_dir / f"{benchmark_id}.md"

    benchmark_result = {
        "benchmark_id": benchmark_id,
        "planner": args.planner,
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "case_results": case_results,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path)
    }

    json_path.write_text(
        json.dumps(benchmark_result, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    write_markdown_report(benchmark_result, markdown_path)

    print("")
    print("=" * 80)
    print("Benchmark complete")
    print(
        json.dumps(
            {
                "benchmark_id": benchmark_id,
                "planner": args.planner,
                "total_cases": total_cases,
                "passed_cases": passed_cases,
                "failed_cases": failed_cases,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path)
            },
            indent=2,
            sort_keys=True
        )
    )

    if failed_cases > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
