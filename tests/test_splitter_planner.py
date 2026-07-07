from app.splitter_planner import (
    is_splitter_prompt,
    plan_splitter_problem,
    extract_outlet1_split_fraction,
)


def test_detects_splitter_prompt():
    assert is_splitter_prompt(
        "Split 10 kg/s of water with 30% going to outlet 1."
    )


def test_extracts_percent_fraction():
    assert extract_outlet1_split_fraction(
        "Split 10 kg/s with 30% going to outlet 1."
    ) == 0.3


def test_plans_splitter_problem():
    spec = plan_splitter_problem(
        "Split 10 kg/s of water with 30% going to outlet 1. What are the outlet flows?"
    )

    assert spec["problem_type"] == "splitter_mass_balance"
    assert spec["mode"] == "calculate_outlet_flows"
    assert spec["inlet_mass_flow_kg_s"] == 10.0
    assert spec["outlet1_split_fraction"] == 0.3


def test_extracts_word_percent():
    assert extract_outlet1_split_fraction(
        "Split 10 kg/s of water with 25 percent going to outlet 1."
    ) == 0.25
