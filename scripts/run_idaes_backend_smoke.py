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
    prompt = "Heat water from 300 K to 350 K at 1 kg/s and report heat duty."

    result = run_problem(
        prompt=prompt,
        planner="regex",
        explain=False,
        repair=False,
        inject_bug=False,
        backend="idaes"
    )

    run_dir = Path(result["run_dir"])
    parsed = load_json(run_dir / "parsed_result.json")
    verification = load_json(run_dir / "verification.json")

    checks = [
        make_check("verified", result.get("verified") is True, result.get("verified")),
        make_check("status_verified", result.get("status") == "verified", result.get("status")),
        make_check("backend", parsed.get("backend") == "idaes", parsed.get("backend")),
        make_check("heat_duty_w", abs(float(parsed.get("heat_duty_w")) - 209200.0) <= 1e-9, parsed.get("heat_duty_w")),
        make_check("idaes_flowsheet_block_created", parsed.get("idaes_flowsheet_block_created") is True, parsed.get("idaes_flowsheet_block_created")),
        make_check("idaes_solver_required", parsed.get("idaes_solver_required") is False, parsed.get("idaes_solver_required")),
        make_check("verification", verification.get("verified") is True, verification.get("verified")),
    ]

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
