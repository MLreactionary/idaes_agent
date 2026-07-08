import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


PROMPT = (
    "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, "
    "source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. "
    "Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost."
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_check(name: str, passed: bool, value):
    return {
        "name": name,
        "passed": bool(passed),
        "value": value
    }


def source_mass(parsed: dict, name: str) -> float:
    for source in parsed["source_results"]:
        if source["name"] == name:
            return float(source["mass_kg"])

    raise KeyError(f"Missing source result for {name}")


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
        make_check("problem_type", parsed.get("problem_type") == "general_blend_cost_optimization", parsed.get("problem_type")),
        make_check("mode", parsed.get("mode") == "minimize_cost", parsed.get("mode")),
        make_check("solver", parsed.get("optimization_solver") == "glpk", parsed.get("optimization_solver")),
        make_check("number_of_sources", int(parsed.get("number_of_sources")) == 3, parsed.get("number_of_sources")),
        make_check("source_A_mass_kg", abs(source_mass(parsed, "A") - 20.0) <= 1e-6, source_mass(parsed, "A")),
        make_check("source_B_mass_kg", abs(source_mass(parsed, "B") - 40.0) <= 1e-6, source_mass(parsed, "B")),
        make_check("source_C_mass_kg", abs(source_mass(parsed, "C") - 40.0) <= 1e-6, source_mass(parsed, "C")),
        make_check("total_cost", abs(float(parsed.get("total_cost")) - 140.0) <= 1e-6, parsed.get("total_cost")),
        make_check("sulfur_result", abs(float(parsed["quality_results"]["sulfur"]) - 0.03) <= 1e-9, parsed["quality_results"]["sulfur"]),
        make_check("ash_result", abs(float(parsed["quality_results"]["ash"]) - 0.02) <= 1e-9, parsed["quality_results"]["ash"]),
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
