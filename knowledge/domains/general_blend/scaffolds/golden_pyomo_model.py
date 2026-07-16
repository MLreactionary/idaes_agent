import json
import pyomo.environ as pyo


SPEC = {
    "objective": "minimize_cost",
    "problem_type": "general_blend_cost_optimization",
    "product_mass_kg": 100.0,
    "quality_lower_bounds": {
        "quality_1": 0.50
    },
    "quality_upper_bounds": {
        "quality_2": 0.10
    },
    "sources": [
        {
            "name": "source_a",
            "cost_per_kg": 2.0,
            "min_required_kg": None,
            "max_available_kg": 80.0,
            "qualities": {
                "quality_1": 0.80,
                "quality_2": 0.05
            },
        },
        {
            "name": "source_b",
            "cost_per_kg": 1.0,
            "min_required_kg": None,
            "max_available_kg": None,
            "qualities": {
                "quality_1": 0.40,
                "quality_2": 0.12
            },
        },
    ],
}

SOLVER_NAME = "glpk"

source_lookup = {
    source["name"]: source
    for source in SPEC["sources"]
}

model = pyo.ConcreteModel()
model.SOURCES = pyo.Set(initialize=list(source_lookup.keys()))


def source_bounds(m, source_name):
    source = source_lookup[source_name]

    lb = source.get("min_required_kg")
    ub = source.get("max_available_kg")

    if lb is None:
        lb = 0.0

    if ub is None:
        return float(lb), None

    return float(lb), float(ub)


model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds)

model.objective = pyo.Objective(
    expr=sum(
        float(source_lookup[source_name]["cost_per_kg"]) * model.mass_kg[source_name]
        for source_name in model.SOURCES
    ),
    sense=pyo.minimize,
)

model.mass_balance = pyo.Constraint(
    expr=sum(
        model.mass_kg[source_name]
        for source_name in model.SOURCES
    )
    == float(SPEC["product_mass_kg"])
)

for quality_name, lower_bound in (SPEC.get("quality_lower_bounds") or {}).items():
    setattr(
        model,
        "quality_lower_" + quality_name,
        pyo.Constraint(
            expr=sum(
                float(source_lookup[source_name]["qualities"].get(quality_name, 0.0))
                * model.mass_kg[source_name]
                for source_name in model.SOURCES
            )
            >= float(lower_bound) * float(SPEC["product_mass_kg"])
        ),
    )

for quality_name, upper_bound in (SPEC.get("quality_upper_bounds") or {}).items():
    setattr(
        model,
        "quality_upper_" + quality_name,
        pyo.Constraint(
            expr=sum(
                float(source_lookup[source_name]["qualities"].get(quality_name, 0.0))
                * model.mass_kg[source_name]
                for source_name in model.SOURCES
            )
            <= float(upper_bound) * float(SPEC["product_mass_kg"])
        ),
    )

solver = pyo.SolverFactory(SOLVER_NAME)
results = solver.solve(model, tee=False)

source_results = {}

for source_name in model.SOURCES:
    source_results[source_name] = float(pyo.value(model.mass_kg[source_name]))

total_mass = sum(source_results.values())

total_cost = sum(
    float(source_lookup[source_name]["cost_per_kg"]) * mass_kg
    for source_name, mass_kg in source_results.items()
)

result = {
    "source_results": source_results,
    "total_cost": float(total_cost),
    "total_blended_mass_kg": float(total_mass),
    "mass_balance_residual_kg": float(total_mass - float(SPEC["product_mass_kg"])),
    "solver_status": str(results.solver.status),
    "termination_condition": str(results.solver.termination_condition),
}

print("RESULT_JSON_START")
print(json.dumps(result, indent=2, sort_keys=True))
print("RESULT_JSON_END")
