from app.model_selector import select_model_for_prompt


def test_selects_utility_sweep_model():
    prompt = (
        "A process needs 500 kW of heat for 1 hr. "
        "Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, "
        "and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. "
        "Sweep emissions caps from 40 to 100 kg CO2/hr in 20 kg steps."
    )

    selection = select_model_for_prompt(prompt)

    assert selection["selected_problem_type"] == "utility_emissions_optimization"
    assert selection["selected_planner_name"] == "utility_optimizer"


def test_selects_general_blend_model():
    prompt = (
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, "
        "source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. "
        "Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost."
    )

    selection = select_model_for_prompt(prompt)

    assert selection["selected_problem_type"] == "general_blend_cost_optimization"
    assert selection["selected_planner_name"] == "general_blend_optimizer"


def test_selects_heater_energy_balance_model():
    prompt = "Heat a water stream from 300 K to 350 K at 1 bar and report heat duty."

    selection = select_model_for_prompt(prompt)

    assert selection["selected_problem_type"] == "heater_energy_balance"


def test_rejects_unsupported_flash_model():
    prompt = "Flash a methane ethane mixture at 300 K and 1 bar and report vapor fraction."

    selection = select_model_for_prompt(prompt)

    assert selection["selected_problem_type"] is None
