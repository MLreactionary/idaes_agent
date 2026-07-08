from app.general_blend_optimizer_planner import (
    is_general_blend_optimization_prompt,
    plan_general_blend_optimization_problem,
)


PROMPT = (
    "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, "
    "source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. "
    "Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost."
)


def test_detects_general_blend_optimization_prompt():
    assert is_general_blend_optimization_prompt(PROMPT)


def test_plans_general_blend_optimization_problem():
    spec = plan_general_blend_optimization_problem(PROMPT)

    assert spec["problem_type"] == "general_blend_cost_optimization"
    assert spec["mode"] == "minimize_cost"
    assert spec["product_mass_kg"] == 100.0

    assert len(spec["sources"]) == 3
    assert spec["quality_limits"] == {
        "ash": 0.02,
        "sulfur": 0.03
    }

    source_a = spec["sources"][0]
    source_b = spec["sources"][1]
    source_c = spec["sources"][2]

    assert source_a["name"] == "A"
    assert source_a["cost_per_kg"] == 2.0
    assert source_a["qualities"] == {
        "ash": 0.02,
        "sulfur": 0.01
    }

    assert source_b["name"] == "B"
    assert source_b["cost_per_kg"] == 1.0
    assert source_b["qualities"] == {
        "ash": 0.01,
        "sulfur": 0.05
    }

    assert source_c["name"] == "C"
    assert source_c["cost_per_kg"] == 1.5
    assert source_c["qualities"] == {
        "ash": 0.03,
        "sulfur": 0.02
    }
