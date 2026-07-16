
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_general_blend_domain_agent import run_domain_agent


CASES = [
    {
        "name": "animal_feed_protein_fiber",
        "prompt": "We need to produce exactly 1,000 kg of animal feed. Corn costs 0.30/kg and contains 9% protein and 2% fiber. Soybean meal costs 0.90/kg and contains 50% protein and 8% fiber. Final mix must contain at least 22% protein and at most 5% fiber. Minimize total cost.",
        "checks": {
            "total_mass": 1000.0,
            "quality_lower": {"protein": 0.22},
            "quality_upper": {"fiber": 0.05},
        },
    },
    {
        "name": "fuel_sulfur_octane",
        "prompt": "Produce exactly 500 kg of gasoline blend. Regular stream costs 0.80 per kg and has sulfur 0.04 and octane 87. Premium stream costs 1.20 per kg and has sulfur 0.01 and octane 95. Reformate costs 1.50 per kg and has sulfur 0.005 and octane 100. Final blend must have sulfur at most 0.02 and octane at least 92. Minimize total cost.",
        "checks": {
            "total_mass": 500.0,
            "quality_lower": {"octane": 0.92},
            "quality_upper": {"sulfur": 0.02},
        },
    },
    {
        "name": "ore_iron_silica",
        "prompt": "Make exactly 200 kg of ore feed. Mine A costs 45 per kg and contains iron 58% and silica 8%. Mine B costs 60 per kg and contains iron 65% and silica 4%. Mine C costs 50 per kg and contains iron 62% and silica 6%. Final feed must contain at least 62% iron and at most 6% silica. Mine B has at most 80 kg available. Minimize total cost.",
        "checks": {
            "total_mass": 200.0,
            "quality_lower": {"iron": 0.62},
            "quality_upper": {"silica": 0.06},
        },
    },
    {
        "name": "chemical_purity_with_availability",
        "prompt": "Blend exactly 100 kg of solvent product. Recovered solvent costs 1.00 per kg and has purity 0.85 and impurity 0.15, but at most 40 kg is available. Fresh solvent costs 3.00 per kg and has purity 0.99 and impurity 0.01. Intermediate solvent costs 2.00 per kg and has purity 0.93 and impurity 0.07. Final product must have purity at least 0.95 and impurity at most 0.05. Minimize total cost.",
        "checks": {
            "total_mass": 100.0,
            "quality_lower": {"purity": 0.95},
            "quality_upper": {"impurity": 0.05},
        },
    },
]


def validate_case(case: dict, result: dict) -> None:
    checks = case["checks"]
    case_name = case["name"]

    if str(result.get("solver_status")) != "ok":
        raise AssertionError("{} solver_status is not ok: {}".format(case_name, result.get("solver_status")))

    if str(result.get("termination_condition")) != "optimal":
        raise AssertionError("{} termination is not optimal: {}".format(case_name, result.get("termination_condition")))

    actual_mass = float(result["total_blended_mass_kg"])
    expected_mass = float(checks["total_mass"])

    if abs(actual_mass - expected_mass) > 1e-4:
        raise AssertionError("{} total mass failed. expected {}, got {}".format(case_name, expected_mass, actual_mass))

    residual = abs(float(result.get("mass_balance_residual_kg", 0.0)))

    if residual > 1e-4:
        raise AssertionError("{} mass balance residual too large: {}".format(case_name, residual))

    quality_results = result.get("quality_results", {})

    for quality, lower in checks.get("quality_lower", {}).items():
        actual = float(quality_results[quality])
        if actual + 1e-6 < float(lower):
            raise AssertionError("{} lower quality failed for {}. actual {}, lower {}".format(case_name, quality, actual, lower))

    for quality, upper in checks.get("quality_upper", {}).items():
        actual = float(quality_results[quality])
        if actual - 1e-6 > float(upper):
            raise AssertionError("{} upper quality failed for {}. actual {}, upper {}".format(case_name, quality, actual, upper))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codegen", choices=["wrapper", "llm"], default="llm")
    parser.add_argument("--solver", default="glpk")
    parser.add_argument("--case", default="all")
    args = parser.parse_args()

    if args.case == "all":
        selected_cases = CASES
    else:
        selected_cases = [case for case in CASES if case["name"] == args.case]

    if not selected_cases:
        raise SystemExit("No matching case: {}".format(args.case))

    summary = []

    for case in selected_cases:
        print("=" * 80)
        print("CASE:", case["name"])
        print("PROMPT:", case["prompt"])

        run = run_domain_agent(case["prompt"], solver_name=args.solver, codegen_mode=args.codegen)
        result = run["result"]

        validate_case(case, result)

        item = {
            "name": case["name"],
            "run_dir": run["run_dir"],
            "total_cost": result.get("total_cost"),
            "quality_results": result.get("quality_results"),
            "source_results": result.get("source_results"),
        }

        summary.append(item)

        print("PASSED:", case["name"])
        print(json.dumps(item, indent=2, sort_keys=True))

    print("=" * 80)
    print("ALL PASSED")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
