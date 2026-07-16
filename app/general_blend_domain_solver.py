
from __future__ import annotations

import json
import math
from typing import Any

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition

from app.llm_spec_extractor import normalize_general_blend_spec, validate_general_blend_spec


class GeneralBlendDomainSolverError(RuntimeError):
    pass


def diagnose_infeasibility(spec: dict[str, Any]) -> dict[str, Any]:
    reasons = []
    product_mass = float(spec["product_mass_kg"])
    sources = spec["sources"]

    total_min = 0.0
    total_max = 0.0
    all_sources_have_max = True

    for source in sources:
        name = source["name"]
        min_required = float(source.get("min_required_kg") or 0.0)
        max_available = source.get("max_available_kg")

        total_min += min_required

        if max_available is None:
            all_sources_have_max = False
        else:
            max_available = float(max_available)
            total_max += max_available

            if min_required > max_available + 1e-9:
                reasons.append(
                    f"Source {name} has minimum required usage {min_required} kg above max availability {max_available} kg."
                )

    if all_sources_have_max and total_max + 1e-9 < product_mass:
        reasons.append(
            f"Total maximum source availability {total_max} kg is below required product mass {product_mass} kg."
        )

    if total_min > product_mass + 1e-9:
        reasons.append(
            f"Total minimum required source usage {total_min} kg exceeds required product mass {product_mass} kg."
        )

    quality_names = set()
    for source in sources:
        quality_names.update(source.get("qualities", {}).keys())

    lower_bounds = spec.get("quality_lower_bounds", {}) or {}
    upper_bounds = spec.get("quality_upper_bounds", {}) or {}

    for quality_name in quality_names:
        values = [
            float(source.get("qualities", {}).get(quality_name, 0.0))
            for source in sources
        ]

        if quality_name in lower_bounds:
            lower = float(lower_bounds[quality_name])
            if max(values) + 1e-9 < lower:
                reasons.append(
                    f"Quality lower bound for {quality_name} is {lower}, but best available source quality is {max(values)}."
                )

        if quality_name in upper_bounds:
            upper = float(upper_bounds[quality_name])
            if min(values) - 1e-9 > upper:
                reasons.append(
                    f"Quality upper bound for {quality_name} is {upper}, but best available source quality is {min(values)}."
                )

        if quality_name in lower_bounds and quality_name in upper_bounds:
            lower = float(lower_bounds[quality_name])
            upper = float(upper_bounds[quality_name])

            if lower > upper + 1e-9:
                reasons.append(
                    f"Quality bounds conflict for {quality_name}: lower bound {lower} is above upper bound {upper}."
                )

    if not reasons:
        reasons.append("Optimization solver reported infeasible, but no simple deterministic diagnosis matched.")

    return {
        "status": "infeasible",
        "reasons": reasons,
    }


def build_model(spec: dict[str, Any]) -> pyo.ConcreteModel:
    model = pyo.ConcreteModel(name="general_blend_domain_agent")

    source_names = [source["name"] for source in spec["sources"]]
    source_lookup = {source["name"]: source for source in spec["sources"]}
    product_mass = float(spec["product_mass_kg"])

    model.SOURCES = pyo.Set(initialize=source_names)

    def source_bounds(model, source_name):
        source = source_lookup[source_name]
        lower = float(source.get("min_required_kg") or 0.0)
        max_available = source.get("max_available_kg")
        upper = None if max_available is None else float(max_available)
        return lower, upper

    model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds)

    def objective_rule(model):
        return sum(
            float(source_lookup[source_name]["cost_per_kg"]) * model.mass_kg[source_name]
            for source_name in model.SOURCES
        )

    model.objective = pyo.Objective(rule=objective_rule, sense=pyo.minimize)

    def mass_balance_rule(model):
        return sum(model.mass_kg[source_name] for source_name in model.SOURCES) == product_mass

    model.mass_balance = pyo.Constraint(rule=mass_balance_rule)

    lower_bounds = spec.get("quality_lower_bounds", {}) or {}
    upper_bounds = spec.get("quality_upper_bounds", {}) or {}

    model.QUALITY_LOWER = pyo.Set(initialize=list(lower_bounds.keys()))
    model.QUALITY_UPPER = pyo.Set(initialize=list(upper_bounds.keys()))

    def quality_value(source_name: str, quality_name: str) -> float:
        return float(source_lookup[source_name].get("qualities", {}).get(quality_name, 0.0))

    def quality_lower_rule(model, quality_name):
        return (
            sum(quality_value(source_name, quality_name) * model.mass_kg[source_name] for source_name in model.SOURCES)
            >= float(lower_bounds[quality_name]) * product_mass
        )

    def quality_upper_rule(model, quality_name):
        return (
            sum(quality_value(source_name, quality_name) * model.mass_kg[source_name] for source_name in model.SOURCES)
            <= float(upper_bounds[quality_name]) * product_mass
        )

    model.quality_lower_constraints = pyo.Constraint(model.QUALITY_LOWER, rule=quality_lower_rule)
    model.quality_upper_constraints = pyo.Constraint(model.QUALITY_UPPER, rule=quality_upper_rule)

    return model


def extract_optimal_result(model: pyo.ConcreteModel, spec: dict[str, Any], solver_name: str, solver_result: Any) -> dict[str, Any]:
    product_mass = float(spec["product_mass_kg"])
    source_lookup = {source["name"]: source for source in spec["sources"]}

    source_results = []

    for source_name in model.SOURCES:
        source = source_lookup[source_name]
        mass_kg = float(pyo.value(model.mass_kg[source_name]))
        cost_per_kg = float(source["cost_per_kg"])
        min_required = source.get("min_required_kg")
        max_available = source.get("max_available_kg")

        source_results.append(
            {
                "name": source_name,
                "mass_kg": mass_kg,
                "cost_per_kg": cost_per_kg,
                "cost": mass_kg * cost_per_kg,
                "qualities": source.get("qualities", {}),
                "min_required_kg": None if min_required is None else float(min_required),
                "max_available_kg": None if max_available is None else float(max_available),
                "minimum_usage_slack_kg": mass_kg - float(min_required or 0.0),
                "availability_slack_kg": None if max_available is None else float(max_available) - mass_kg,
            }
        )

    total_mass = sum(source["mass_kg"] for source in source_results)
    total_cost = sum(source["cost"] for source in source_results)

    quality_names = set()
    for source in source_results:
        quality_names.update(source.get("qualities", {}).keys())

    quality_results = {}

    for quality_name in sorted(quality_names):
        quality_results[quality_name] = sum(
            float(source.get("qualities", {}).get(quality_name, 0.0)) * source["mass_kg"]
            for source in source_results
        ) / total_mass

    lower_bounds = spec.get("quality_lower_bounds", {}) or {}
    upper_bounds = spec.get("quality_upper_bounds", {}) or {}

    quality_lower_slacks = {
        name: quality_results[name] - float(bound)
        for name, bound in lower_bounds.items()
    }

    quality_upper_slacks = {
        name: float(bound) - quality_results[name]
        for name, bound in upper_bounds.items()
    }

    maximum_quality_lower_violation = max([max(-slack, 0.0) for slack in quality_lower_slacks.values()] or [0.0])
    maximum_quality_upper_violation = max([max(-slack, 0.0) for slack in quality_upper_slacks.values()] or [0.0])

    maximum_minimum_usage_violation_kg = max(
        [max(-source["minimum_usage_slack_kg"], 0.0) for source in source_results] or [0.0]
    )

    maximum_source_availability_violation_kg = max(
        [
            max(-source["availability_slack_kg"], 0.0)
            for source in source_results
            if source["availability_slack_kg"] is not None
        ] or [0.0]
    )

    return {
        "problem_type": "general_blend_cost_optimization",
        "mode": "domain_agent_minimize_cost",
        "backend": "pyomo",
        "solver_name": solver_name,
        "optimization_solver": solver_name,
        "solver_status": "ok",
        "termination_condition": str(solver_result.solver.termination_condition),
        "product_mass_kg": product_mass,
        "total_blended_mass_kg": total_mass,
        "mass_balance_residual_kg": product_mass - total_mass,
        "number_of_sources": len(source_results),
        "source_results": source_results,
        "quality_results": quality_results,
        "quality_lower_bounds": lower_bounds,
        "quality_upper_bounds": upper_bounds,
        "quality_lower_slacks": quality_lower_slacks,
        "quality_upper_slacks": quality_upper_slacks,
        "maximum_quality_lower_violation": maximum_quality_lower_violation,
        "maximum_quality_upper_violation": maximum_quality_upper_violation,
        "maximum_minimum_usage_violation_kg": maximum_minimum_usage_violation_kg,
        "maximum_source_availability_violation_kg": maximum_source_availability_violation_kg,
        "total_cost": total_cost,
    }


def solve_general_blend_spec(spec: dict[str, Any], solver_name: str = "glpk") -> dict[str, Any]:
    normalized = normalize_general_blend_spec(spec)
    errors = validate_general_blend_spec(normalized)

    if errors:
        raise GeneralBlendDomainSolverError("Invalid general blend spec: " + "; ".join(errors))

    model = build_model(normalized)
    solver = pyo.SolverFactory(solver_name)

    if not solver.available(False):
        raise GeneralBlendDomainSolverError(f"Solver is not available: {solver_name}")

    solver_result = solver.solve(model, tee=False)

    status = solver_result.solver.status
    termination = solver_result.solver.termination_condition

    if status == SolverStatus.ok and termination in {TerminationCondition.optimal, TerminationCondition.locallyOptimal}:
        return extract_optimal_result(model, normalized, solver_name, solver_result)

    if termination in {TerminationCondition.infeasible, TerminationCondition.infeasibleOrUnbounded}:
        return {
            "problem_type": "general_blend_cost_optimization",
            "mode": "domain_agent_minimize_cost",
            "backend": "pyomo",
            "solver_name": solver_name,
            "optimization_solver": solver_name,
            "solver_status": "infeasible",
            "termination_condition": "infeasible",
            "infeasibility_diagnosis": diagnose_infeasibility(normalized),
        }

    deterministic_diagnosis = diagnose_infeasibility(normalized)
    real_reasons = [
        reason
        for reason in deterministic_diagnosis.get("reasons", [])
        if not reason.startswith("Optimization solver reported infeasible")
    ]

    if real_reasons:
        deterministic_diagnosis["reasons"] = real_reasons

        return {
            "problem_type": "general_blend_cost_optimization",
            "mode": "domain_agent_minimize_cost",
            "backend": "pyomo",
            "solver_name": solver_name,
            "optimization_solver": solver_name,
            "solver_status": "infeasible",
            "termination_condition": "infeasible",
            "infeasibility_diagnosis": deterministic_diagnosis,
        }

    return {
        "problem_type": "general_blend_cost_optimization",
        "mode": "domain_agent_minimize_cost",
        "backend": "pyomo",
        "solver_name": solver_name,
        "optimization_solver": solver_name,
        "solver_status": "nonoptimal",
        "termination_condition": str(termination),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("spec_json_path")
    parser.add_argument("--solver", default="glpk")

    args = parser.parse_args()

    with open(args.spec_json_path, "r", encoding="utf-8") as handle:
        spec = json.load(handle)

    result = solve_general_blend_spec(spec, solver_name=args.solver)

    print("RESULT_JSON_START")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("RESULT_JSON_END")


if __name__ == "__main__":
    main()
