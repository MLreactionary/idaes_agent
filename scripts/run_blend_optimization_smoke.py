import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


PROMPT = (
    "Optimize a blend of 100 kg product using source A cost 2 $/kg impurity 1% "
    "and source B cost 1 $/kg impurity 5%, with final impurity limit 3%. "
    "What is the minimum cost blend?"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_check(name: str, passed: bool, value):
    return {
        "name": name,
        "passed": bool(passed),
        "value": value
    }


def main():
    result = run_problem(
        prompt=PROMPT,
        planner="llm",
        explain=False,
        repair=False,
        inject_bug=False,
    )

    run_dir = Path(result["run_dir"])
    parsed = load_json(run_dir / "parsed_result.json")
    verification = load_json(run_dir / "verification.json")

    checks = [
        make_check("verified", result.get("verified") is True, result.get("verified")),
        make_check("status_verified", result.get("status") == "verified", result.get("status")),
        make_check("problem_type", parsed.get("problem_type") == "blend_cost_optimization", parsed.get("problem_type")),
        make_check("mode", parsed.get("mode") == "minimize_cost", parsed.get("mode")),
        make_check("solver", parsed.get("optimization_solver") == "glpk", parsed.get("optimization_solver")),
        make_check("source1_mass_kg", abs(float(parsed.get("source1_mass_kg")) - 50.0) <= 1e-6, parsed.get("source1_mass_kg")),
        make_check("source2_mass_kg", abs(float(parsed.get("source2_mass_kg")) - 50.0) <= 1e-6, parsed.get("source2_mass_kg")),
        make_check("total_cost", abs(float(parsed.get("total_cost")) - 150.0) <= 1e-6, parsed.get("total_cost")),
        make_check("final_impurity_fraction", abs(float(parsed.get("final_impurity_fraction")) - 0.03) <= 1e-9, parsed.get("final_impurity_fraction")),
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
