from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_general_blend_domain_agent import run_domain_agent


DEFAULT_CASES_PATH = PROJECT_ROOT / "benchmarks" / "linear_blend" / "cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "benchmarks" / "linear_blend"


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def is_infeasible_text(text: str) -> bool:
    lowered = text.lower()
    return (
        "infeasible" in lowered
        or "no feasible" in lowered
        or "no value for uninitialized" in lowered
        or "uninitialized vardata" in lowered
    )


def evaluate_case_result(
    case: dict[str, Any],
    run_payload: dict[str, Any] | None,
    error_message: str | None,
    violation_tolerance: float,
) -> tuple[bool, dict[str, Any]]:
    expected_status = case.get("expected_status", "optimal")

    details: dict[str, Any] = {
        "expected_status": expected_status,
        "passed": False,
        "reason": "",
    }

    if error_message is not None:
        details["error_message"] = error_message

        if expected_status == "infeasible" and is_infeasible_text(error_message):
            details["passed"] = True
            details["reason"] = "Expected infeasible case failed during solve or value extraction."
            return True, details

        details["reason"] = "Run raised an exception."
        return False, details

    if run_payload is None:
        details["reason"] = "No run payload returned."
        return False, details

    result = run_payload.get("result", {})
    solver_status = str(result.get("solver_status", "")).lower()
    termination = str(result.get("termination_condition", "")).lower()
    max_violation = numeric(result.get("maximum_constraint_violation"), default=999.0)

    details.update(
        {
            "solver_status": result.get("solver_status"),
            "termination_condition": result.get("termination_condition"),
            "total_cost": result.get("total_cost"),
            "maximum_constraint_violation": max_violation,
            "run_dir": run_payload.get("run_dir"),
        }
    )

    if expected_status == "infeasible":
        if "infeasible" in solver_status or "infeasible" in termination:
            details["passed"] = True
            details["reason"] = "Expected infeasible and solver reported infeasible."
            return True, details

        details["reason"] = "Expected infeasible, but solver returned a feasible-looking result."
        return False, details

    if solver_status != "ok":
        details["reason"] = "Solver status was not ok."
        return False, details

    if termination != "optimal":
        details["reason"] = "Termination condition was not optimal."
        return False, details

    if max_violation > violation_tolerance:
        details["reason"] = "Maximum constraint violation exceeded tolerance."
        return False, details

    details["passed"] = True
    details["reason"] = "Optimal result verified."
    return True, details


def run_benchmark(
    cases_path: Path,
    codegen_mode: str,
    solver_name: str,
    max_cases: int | None,
    violation_tolerance: float,
) -> dict[str, Any]:
    cases = load_cases(cases_path)

    if max_cases is not None:
        cases = cases[:max_cases]

    records = []

    for index, case in enumerate(cases, start=1):
        print("=" * 80)
        print(f"CASE {index}/{len(cases)}: {case['name']}")
        print(f"DIFFICULTY: {case.get('difficulty')}")
        print(f"EXPECTED: {case.get('expected_status')}")

        start_time = time.time()
        run_payload = None
        error_message = None

        try:
            run_payload = run_domain_agent(
                case["prompt"],
                solver_name=solver_name,
                codegen_mode=codegen_mode,
            )
        except Exception as exc:
            error_message = "".join(
                traceback.format_exception_only(type(exc), exc)
            ).strip()

        elapsed_seconds = time.time() - start_time

        passed, details = evaluate_case_result(
            case=case,
            run_payload=run_payload,
            error_message=error_message,
            violation_tolerance=violation_tolerance,
        )

        record = {
            "name": case["name"],
            "difficulty": case.get("difficulty"),
            "family": case.get("family"),
            "expected_status": case.get("expected_status"),
            "passed": passed,
            "elapsed_seconds": elapsed_seconds,
            **details,
        }

        records.append(record)

        if passed:
            print(f"PASSED: {case['name']}")
        else:
            print(f"FAILED: {case['name']}")
            print(f"REASON: {record.get('reason')}")

        if record.get("total_cost") is not None:
            print(f"TOTAL_COST: {record['total_cost']}")

        if record.get("maximum_constraint_violation") is not None:
            print(f"MAX_VIOLATION: {record['maximum_constraint_violation']}")

    total = len(records)
    passed_count = sum(1 for record in records if record["passed"])

    by_difficulty: dict[str, dict[str, int]] = {}

    for record in records:
        difficulty = str(record.get("difficulty", "unknown"))
        if difficulty not in by_difficulty:
            by_difficulty[difficulty] = {"passed": 0, "total": 0}

        by_difficulty[difficulty]["total"] += 1

        if record["passed"]:
            by_difficulty[difficulty]["passed"] += 1

    summary = {
        "codegen_mode": codegen_mode,
        "solver_name": solver_name,
        "cases_path": str(cases_path),
        "total_cases": total,
        "passed_cases": passed_count,
        "failed_cases": total - passed_count,
        "pass_rate": passed_count / total if total else 0.0,
        "by_difficulty": by_difficulty,
        "records": records,
    }

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DEFAULT_OUTPUT_DIR / f"benchmark_{codegen_mode}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True))

    print("=" * 80)
    print("SUMMARY")
    print(json.dumps({k: v for k, v in summary.items() if k != "records"}, indent=2))
    print(f"Saved benchmark result to {output_path}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES_PATH))
    parser.add_argument("--codegen", choices=["wrapper", "llm"], default="wrapper")
    parser.add_argument("--solver", default="glpk")
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--violation-tolerance", type=float, default=1e-6)
    args = parser.parse_args()

    run_benchmark(
        cases_path=Path(args.cases),
        codegen_mode=args.codegen,
        solver_name=args.solver,
        max_cases=args.max_cases,
        violation_tolerance=args.violation_tolerance,
    )


if __name__ == "__main__":
    main()
