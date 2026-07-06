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


def check_expected(case: dict, run_result: dict) -> list[dict]:
    """
    Benchmark-level checks.

    These are separate from the engineering verifier.
    The verifier checks whether the generated model result is internally valid.
    These checks compare the result to expected answers for benchmark prompts.
    """
    checks = []

    run_dir = Path(run_result["run_dir"])
    parsed_result_path = run_dir / "parsed_result.json"
    structured_spec_path = run_dir / "structured_spec.json"

    parsed = load_json(parsed_result_path)
    spec = load_json(structured_spec_path)

    tolerance = float(case.get("tolerance_abs", 1e-6))

    if "expected_mode" in case:
        observed = spec.get("mode")
        expected = case["expected_mode"]
        checks.append(
            {
                "name": "expected_mode",
                "passed": observed == expected,
                "expected": expected,
                "observed": observed
            }
        )

    if "expected_heat_duty_w" in case:
        observed = parsed.get("heat_duty_w")
        expected = float(case["expected_heat_duty_w"])
        passed = isinstance(observed, (int, float)) and abs(observed - expected) <= tolerance
        checks.append(
            {
                "name": "expected_heat_duty_w",
                "passed": passed,
                "expected": expected,
                "observed": observed,
                "abs_error": None if not isinstance(observed, (int, float)) else abs(observed - expected),
                "tolerance": tolerance
            }
        )

    if "expected_temperature_out_k" in case:
        observed = parsed.get("temperature_out_k")
        expected = float(case["expected_temperature_out_k"])
        passed = isinstance(observed, (int, float)) and abs(observed - expected) <= tolerance
        checks.append(
            {
                "name": "expected_temperature_out_k",
                "passed": passed,
                "expected": expected,
                "observed": observed,
                "abs_error": None if not isinstance(observed, (int, float)) else abs(observed - expected),
                "tolerance": tolerance
            }
        )

    return checks


def write_markdown_report(summary: dict, output_path: Path) -> None:
    lines = []

    lines.append("# Heater MVP Benchmark Report")
    lines.append("")
    lines.append(f"- Planner: `{summary['planner']}`")
    lines.append(f"- Created at: `{summary['created_at']}`")
    lines.append(f"- Total cases: `{summary['total_cases']}`")
    lines.append(f"- Passed cases: `{summary['passed_cases']}`")
    lines.append(f"- Failed cases: `{summary['failed_cases']}`")
    lines.append("")

    lines.append("| Case | Expected Error | Outcome | Verified | Benchmark Checks | Run ID |")
    lines.append("|---|---:|---|---:|---:|---|")

    for result in summary["results"]:
        case_id = result["id"]
        expected_error = result["expect_error"]
        outcome = result["outcome"]
        verified = result.get("verified")
        benchmark_passed = result.get("benchmark_passed")
        run_id = result.get("run_id", "")

        lines.append(
            f"| `{case_id}` | `{expected_error}` | `{outcome}` | `{verified}` | `{benchmark_passed}` | `{run_id}` |"
        )

    lines.append("")

    lines.append("## Details")
    lines.append("")

    for result in summary["results"]:
        lines.append(f"### {result['id']}")
        lines.append("")
        lines.append(f"Prompt: {result['prompt']}")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result, indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def run_benchmark(cases_path: Path, planner: str) -> dict:
    cases = load_json(cases_path)

    created_at = datetime.now().isoformat(timespec="seconds")
    benchmark_id = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    output_dir = PROJECT_ROOT / "outputs" / "benchmarks"
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []

    for case in cases:
        case_id = case["id"]
        prompt = case["prompt"]
        expect_error = bool(case.get("expect_error", False))

        print("-" * 80)
        print(f"Running case: {case_id}")
        print(f"Prompt: {prompt}")

        try:
            run_result = run_problem(prompt, planner=planner)

            expected_checks = check_expected(case, run_result)
            expected_checks_passed = all(check["passed"] for check in expected_checks)

            if expect_error:
                case_passed = False
                outcome = "unexpected_success"
            else:
                case_passed = bool(run_result["verified"]) and expected_checks_passed
                outcome = "passed" if case_passed else "failed_expected_check"

            result = {
                "id": case_id,
                "prompt": prompt,
                "expect_error": expect_error,
                "outcome": outcome,
                "case_passed": case_passed,
                "benchmark_passed": expected_checks_passed,
                "planner": planner,
                "run_id": run_result["run_id"],
                "run_dir": run_result["run_dir"],
                "report_path": run_result["report_path"],
                "status": run_result["status"],
                "verified": run_result["verified"],
                "num_failures": run_result["num_failures"],
                "expected_checks": expected_checks
            }

        except Exception as exc:
            if expect_error:
                case_passed = True
                outcome = "expected_error"
            else:
                case_passed = False
                outcome = "unexpected_error"

            result = {
                "id": case_id,
                "prompt": prompt,
                "expect_error": expect_error,
                "outcome": outcome,
                "case_passed": case_passed,
                "benchmark_passed": case_passed,
                "planner": planner,
                "error_type": type(exc).__name__,
                "error_message": str(exc)
            }

        print(f"Outcome: {result['outcome']}")
        print(f"Case passed: {result['case_passed']}")

        results.append(result)

    passed_cases = sum(1 for r in results if r["case_passed"])
    total_cases = len(results)
    failed_cases = total_cases - passed_cases

    summary = {
        "benchmark_id": benchmark_id,
        "created_at": created_at,
        "planner": planner,
        "cases_path": str(cases_path),
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": failed_cases,
        "results": results
    }

    json_path = output_dir / f"{benchmark_id}.json"
    md_path = output_dir / f"{benchmark_id}.md"

    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_markdown_report(summary, md_path)

    summary["json_path"] = str(json_path)
    summary["markdown_path"] = str(md_path)

    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cases",
        default="benchmarks/heater_mvp_prompts.json",
        help="Path to benchmark cases JSON."
    )
    parser.add_argument(
        "--planner",
        choices=["llm", "regex"],
        default="llm",
        help="Planner to benchmark."
    )

    args = parser.parse_args()

    summary = run_benchmark(
        cases_path=PROJECT_ROOT / args.cases,
        planner=args.planner
    )

    print("")
    print("=" * 80)
    print("Benchmark complete")
    print(json.dumps(
        {
            "benchmark_id": summary["benchmark_id"],
            "planner": summary["planner"],
            "total_cases": summary["total_cases"],
            "passed_cases": summary["passed_cases"],
            "failed_cases": summary["failed_cases"],
            "json_path": summary["json_path"],
            "markdown_path": summary["markdown_path"]
        },
        indent=2,
        sort_keys=True
    ))


if __name__ == "__main__":
    main()
