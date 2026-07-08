import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


PROMPT = (
    "A process needs 500 kW of heat for 1 hr. "
    "Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, "
    "and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. "
    "Emissions must be at most 60 kg CO2/hr. Minimize cost."
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_check(name: str, passed: bool, value):
    return {
        "name": name,
        "passed": bool(passed),
        "value": value
    }


def utility_heat(parsed: dict, name: str) -> float:
    for utility in parsed["utility_results"]:
        if utility["name"] == name:
            return float(utility["heat_kwh"])

    raise KeyError(f"Missing utility result for {name}")


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
        make_check("problem_type", parsed.get("problem_type") == "utility_emissions_optimization", parsed.get("problem_type")),
        make_check("mode", parsed.get("mode") == "minimize_cost_with_emissions_cap", parsed.get("mode")),
        make_check("solver", parsed.get("optimization_solver") == "glpk", parsed.get("optimization_solver")),
        make_check("number_of_utilities", int(parsed.get("number_of_utilities")) == 2, parsed.get("number_of_utilities")),
        make_check("steam_heat_kwh", abs(utility_heat(parsed, "steam") - 233.333333333333) <= 1e-6, utility_heat(parsed, "steam")),
        make_check("electric_heat_kwh", abs(utility_heat(parsed, "electric_heat") - 266.666666666667) <= 1e-6, utility_heat(parsed, "electric_heat")),
        make_check("total_cost", abs(float(parsed.get("total_cost")) - 30.6666666666667) <= 1e-6, parsed.get("total_cost")),
        make_check("total_emissions", abs(float(parsed.get("total_emissions_kg_co2")) - 60.0) <= 1e-6, parsed.get("total_emissions_kg_co2")),
        make_check("emissions_violation", abs(float(parsed.get("emissions_violation_kg_co2"))) <= 1e-9, parsed.get("emissions_violation_kg_co2")),
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
