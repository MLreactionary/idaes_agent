import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


def main():
    prompt = "Heat water from 300 K to 350 K at 1 bar and report heat duty."

    result = run_problem(
        prompt=prompt,
        planner="llm",
        explain=False,
        repair=True,
        inject_bug=True,
        max_repair_attempts=1
    )

    checks = []

    checks.append({
        "name": "verified",
        "passed": result.get("verified") is True,
        "value": result.get("verified")
    })

    checks.append({
        "name": "status_verified",
        "passed": result.get("status") == "verified",
        "value": result.get("status")
    })

    checks.append({
        "name": "repair_attempts_used",
        "passed": result.get("repair_attempts_used") == 1,
        "value": result.get("repair_attempts_used")
    })

    run_dir = Path(result["run_dir"])

    expected_files = [
        "injected_bug.json",
        "repair_attempt_1_before.py",
        "repair_attempt_1_candidate.py",
        "repair_attempt_1_patched.py",
        "repair_attempt_1_trace.json",
        "report.md",
        "verification.json"
    ]

    for filename in expected_files:
        path = run_dir / filename
        checks.append({
            "name": f"file_exists_{filename}",
            "passed": path.exists(),
            "value": str(path)
        })

    report_text = (run_dir / "report.md").read_text(encoding="utf-8")

    checks.append({
        "name": "report_has_repair_history",
        "passed": "## Repair History" in report_text,
        "value": "## Repair History" in report_text
    })

    trace = json.loads(
        (run_dir / "repair_attempt_1_trace.json").read_text(encoding="utf-8")
    )

    allowed_patch_strategies = {
        "minimal_import_patch_from_llm_candidate",
        "minimal_import_patch_deterministic",
    }

    checks.append({
        "name": "patch_strategy",
        "passed": trace.get("patch_strategy") in allowed_patch_strategies,
        "value": trace.get("patch_strategy")
    })

    passed = all(check["passed"] for check in checks)

    output = {
        "passed": passed,
        "run_id": result["run_id"],
        "run_dir": result["run_dir"],
        "checks": checks
    }

    print(json.dumps(output, indent=2, sort_keys=True))

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
