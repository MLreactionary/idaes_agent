from app.spec_reconciler import (
    extract_temperatures_k,
    extract_mass_flow_kg_s,
    extract_heat_duty_w,
    reconcile_spec_with_prompt,
)


def test_extract_celsius_temperatures():
    temps = extract_temperatures_k("Cool water from 80 C to 30 C.")
    assert temps == [353.15, 303.15]


def test_extract_mass_flow():
    mass_flow = extract_mass_flow_kg_s("Cool water at 2 kg/s.")
    assert mass_flow == 2.0


def test_heat_removed_is_negative():
    heat_duty = extract_heat_duty_w("Water enters at 350 K and 50 kW of heat is removed.")
    assert heat_duty == -50000.0


def test_heat_received_is_positive():
    heat_duty = extract_heat_duty_w("Water enters at 300 K and receives 100 kW of heat.")
    assert heat_duty == 100000.0


def test_reconciles_bad_outlet_temperature():
    prompt = "Cool water from 80 C to 30 C at 2 kg/s and report the heat duty."

    spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "material": "water",
        "mass_flow_kg_s": 2.0,
        "temperature_in_k": 353.15,
        "temperature_out_k": 323.15
    }

    reconciled, changes = reconcile_spec_with_prompt(spec, prompt)

    assert reconciled["temperature_in_k"] == 353.15
    assert reconciled["temperature_out_k"] == 303.15
    assert reconciled["mass_flow_kg_s"] == 2.0
    assert any(change["field"] == "temperature_out_k" for change in changes)
