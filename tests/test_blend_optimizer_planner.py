from app.blend_optimizer_planner import (
    is_blend_optimization_prompt,
    plan_blend_optimization_problem,
)


PROMPT = (
    "Optimize a blend of 100 kg product using source A cost 2 $/kg impurity 1% "
    "and source B cost 1 $/kg impurity 5%, with final impurity limit 3%. "
    "What is the minimum cost blend?"
)


def test_detects_blend_optimization_prompt():
    assert is_blend_optimization_prompt(PROMPT)


def test_plans_blend_optimization_problem():
    spec = plan_blend_optimization_problem(PROMPT)

    assert spec["problem_type"] == "blend_cost_optimization"
    assert spec["mode"] == "minimize_cost"
    assert spec["product_mass_kg"] == 100.0

    assert spec["source1_name"] == "A"
    assert spec["source1_cost_per_kg"] == 2.0
    assert spec["source1_impurity_fraction"] == 0.01

    assert spec["source2_name"] == "B"
    assert spec["source2_cost_per_kg"] == 1.0
    assert spec["source2_impurity_fraction"] == 0.05

    assert spec["impurity_limit_fraction"] == 0.03
