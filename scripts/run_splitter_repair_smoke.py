import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_check(name: str, passed: bool, value):
    return {
        "name": name,
        "passed": bool(passed),
        "value": value
    }


def main():
    prompt = "Split 10 kg/s of water with 30% going to outlet 1. What are the outlet flows?"

    result = run_problem(
        prompt=prompt,
        planner="llm",
        explain=False,
        repair=True,
        inject_bug=True,
        inject_bug_type="splitter_wrong_split_key",
        max_repair_attempts=1
    )

    run_dir = Path(result["run_dir"])
    parsed_result = load_json(run_dir / "parsed_result.json")
    verification = load_json(run_dir / "verification.json")
    trace = load_json(run_dir / "repair_attempt_1_trace.json")
    injected_bug = load_json(run_dir / "injected_bug.json")
    report_text = (run_dir / "report.md").read_text(encoding="utf-8")

    checks = []

    checks.append(make_check(
        "verified",
        result.get("verified") is True,
        result.get("verified")
    ))

    checks.append(make_check(
        "status_verified",
        result.get("status") == "verified",
        result.get("status")
    ))

    checks.append(make_check(
        "repair_attempts_used",
        result.get("repair_attempts_used") == 1,
        result.get("repair_attempts_used")
    ))

    checks.append(make_check(
        "bug_type",
        injected_bug.get("bug_type") == "splitter_wrong_split_key",
        injected_bug.get("bug_type")
    ))

    checks.append(make_check(
        "patch_strategy",
        trace.get("patch_strategy") == "minimal_splitter_key_patch_deterministic",
        trace.get("patch_strategy")
    ))

    checks.append(make_check(
        "outlet1_mass_flow_kg_s",
        abs(float(parsed_result.get("outlet1_mass_flow_kg_s")) - 3.0) <= 1e-9,
        parsed_result.get("outlet1_mass_flow_kg_s")
    ))

    checks.append(make_check(
        "outlet2_mass_flow_kg_s",
        abs(float(parsed_result.get("outlet2_mass_flow_kg_s")) - 7.0) <= 1e-9,
        parsed_result.get("outlet2_mass_flow_kg_s")
    ))

    checks.append(make_check(
        "mass_balance_verified",
        verification.get("verified") is True,
        verification.get("verified")
    ))

    checks.append(make_check(
        "report_has_repair_history",
        "## Repair History" in report_text,
        "## Repair History" in report_text
    ))

    passed = all(check["passed"] for check in checks)

    summary = {
        "passed": passed,
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "checks": checks
    }

    print(json.dumps(summary, indent=2, sort_keys=True))

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
