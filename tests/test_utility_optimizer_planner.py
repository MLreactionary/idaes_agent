from app.utility_optimizer_planner import (
    is_utility_optimization_prompt,
    plan_utility_optimization_problem,
)


PROMPT = (
    "A process needs 500 kW of heat for 1 hr. "
    "Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, "
    "and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. "
    "Emissions must be at most 60 kg CO2/hr. Minimize cost."
)


def test_detects_utility_optimization_prompt():
    assert is_utility_optimization_prompt(PROMPT)


def test_plans_utility_optimization_problem():
    spec = plan_utility_optimization_problem(PROMPT)

    assert spec["problem_type"] == "utility_emissions_optimization"
    assert spec["mode"] == "minimize_cost_with_emissions_cap"
    assert spec["heat_demand_kwh"] == 500.0
    assert spec["emissions_cap_kg_co2"] == 60.0

    assert len(spec["utilities"]) == 2

    steam = spec["utilities"][0]
    electric = spec["utilities"][1]

    assert steam["name"] == "steam"
    assert steam["cost_per_kwh"] == 0.04
    assert steam["emissions_kg_co2_per_kwh"] == 0.2

    assert electric["name"] == "electric_heat"
    assert electric["cost_per_kwh"] == 0.08
    assert electric["emissions_kg_co2_per_kwh"] == 0.05



SWEEP_PROMPT = (
    "A process needs 500 kW of heat for 1 hr. "
    "Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, "
    "and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. "
    "Sweep emissions caps from 40 to 100 kg CO2/hr in 20 kg steps and report the cost emissions tradeoff."
)


def test_plans_utility_emissions_cap_sweep():
    spec = plan_utility_optimization_problem(SWEEP_PROMPT)

    assert spec["problem_type"] == "utility_emissions_optimization"
    assert spec["mode"] == "sweep_emissions_cap"
    assert spec["heat_demand_kwh"] == 500.0
    assert spec["emissions_cap_values_kg_co2"] == [40.0, 60.0, 80.0, 100.0]
    assert len(spec["utilities"]) == 2



MULTI_PERIOD_PROMPT = (
    "Period 1 needs 500 kW of heat for 1 hr, period 2 needs 300 kW of heat for 1 hr. "
    "Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, "
    "and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. "
    "Total emissions must be at most 100 kg CO2. Minimize cost."
)


def test_plans_multi_period_utility_optimization():
    spec = plan_utility_optimization_problem(MULTI_PERIOD_PROMPT)

    assert spec["problem_type"] == "utility_emissions_optimization"
    assert spec["mode"] == "multi_period_minimize_cost_with_emissions_cap"
    assert spec["total_emissions_cap_kg_co2"] == 100.0
    assert spec["periods"] == [
        {"name": "period_1", "heat_demand_kwh": 500.0},
        {"name": "period_2", "heat_demand_kwh": 300.0},
    ]
    assert len(spec["utilities"]) == 2
