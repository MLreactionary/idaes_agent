from app.mixer_planner import (
    is_mixer_prompt,
    extract_all_mass_flows_kg_s,
    plan_mixer_problem,
)


def test_is_mixer_prompt():
    assert is_mixer_prompt("Mix 1 kg/s water with 2 kg/s water.")
    assert is_mixer_prompt("Combine two water streams.")
    assert not is_mixer_prompt("Heat water from 300 K to 350 K.")


def test_extract_all_mass_flows_kg_s():
    values = extract_all_mass_flows_kg_s(
        "Mix 3600 kg/hr of water with 500 g/s of water."
    )

    assert abs(values[0] - 1.0) < 1e-12
    assert abs(values[1] - 0.5) < 1e-12


def test_plan_mixer_problem_kelvin():
    spec = plan_mixer_problem(
        "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?"
    )

    assert spec["problem_type"] == "adiabatic_mixer"
    assert spec["mode"] == "calculate_outlet_temperature"
    assert spec["stream1_mass_flow_kg_s"] == 1.0
    assert spec["stream2_mass_flow_kg_s"] == 2.0
    assert spec["stream1_temperature_k"] == 300.0
    assert spec["stream2_temperature_k"] == 360.0
    assert spec["stream1_cp_j_kg_k"] == 4184.0
    assert spec["stream2_cp_j_kg_k"] == 4184.0


def test_plan_mixer_problem_celsius():
    spec = plan_mixer_problem(
        "Mix 1 kg/s of water at 25 C with 1 kg/s of water at 75 C. What is the outlet temperature?"
    )

    assert abs(spec["stream1_temperature_k"] - 298.15) < 1e-12
    assert abs(spec["stream2_temperature_k"] - 348.15) < 1e-12


def test_detects_blend_prompt_as_mixer():
    assert is_mixer_prompt(
        "Blend 3600 kg/hr of water at 25 C with 0.5 kg/s of water at 75 C."
    )


def test_mixer_rich_units_celsius_and_kg_hr():
    spec = plan_mixer_problem(
        "Blend 3600 kg/hr of water at 25 C with 0.5 kg/s of water at 75 C. What is the outlet temperature?"
    )

    assert spec["problem_type"] == "adiabatic_mixer"
    assert spec["mode"] == "calculate_outlet_temperature"
    assert abs(spec["stream1_mass_flow_kg_s"] - 1.0) < 1e-9
    assert abs(spec["stream2_mass_flow_kg_s"] - 0.5) < 1e-9
    assert abs(spec["stream1_temperature_k"] - 298.15) < 1e-9
    assert abs(spec["stream2_temperature_k"] - 348.15) < 1e-9
