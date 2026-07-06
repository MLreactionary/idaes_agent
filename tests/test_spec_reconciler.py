from app.spec_reconciler import (
    extract_temperatures_k,
    extract_mass_flow_kg_s,
    extract_cp_j_kg_k,
    extract_pressure_pa,
    extract_heat_duty_w,
    reconcile_spec_with_prompt,
)


def test_extract_temperatures_celsius_to_kelvin():
    temps = extract_temperatures_k("Heat water from 25 C to 80 C.")
    assert temps == [298.15, 353.15]


def test_extract_temperatures_fahrenheit_to_kelvin():
    temps = extract_temperatures_k("Heat water from 68 F to 212 F.")
    assert abs(temps[0] - 293.15) < 1e-9
    assert abs(temps[1] - 373.15) < 1e-9


def test_extract_mass_flow_kg_hr_to_kg_s():
    value = extract_mass_flow_kg_s("Heat 3600 kg/hr of water.")
    assert abs(value - 1.0) < 1e-12


def test_extract_mass_flow_g_s_to_kg_s():
    value = extract_mass_flow_kg_s("Heat 500 g/s of water.")
    assert abs(value - 0.5) < 1e-12


def test_extract_cp_kj_kg_k_to_j_kg_k():
    value = extract_cp_j_kg_k("Use Cp = 4.18 kJ/kg/K.")
    assert abs(value - 4180.0) < 1e-12


def test_extract_pressure_kpa_to_pa():
    value = extract_pressure_pa("at 101.325 kPa")
    assert abs(value - 101325.0) < 1e-12


def test_extract_heat_duty_mw_to_w():
    value = extract_heat_duty_w("Water receives 2 MW of heat.")
    assert abs(value - 2_000_000.0) < 1e-12


def test_extract_heat_removed_is_negative():
    value = extract_heat_duty_w("Water enters at 350 K and 50 kW of heat is removed.")
    assert abs(value + 50_000.0) < 1e-12


def test_reconcile_rich_engineering_units():
    spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "material": "water",
        "flow_basis": "mass",
        "mass_flow_kg_s": 1.0,
        "cp_j_kg_k": 4184.0,
        "pressure_pa": 100000.0,
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0,
    }

    prompt = "Heat 3600 kg/hr of water from 25 C to 80 C at 101.325 kPa using Cp = 4.18 kJ/kg/K."

    reconciled, changes = reconcile_spec_with_prompt(spec, prompt)

    assert abs(reconciled["mass_flow_kg_s"] - 1.0) < 1e-12
    assert abs(reconciled["temperature_in_k"] - 298.15) < 1e-12
    assert abs(reconciled["temperature_out_k"] - 353.15) < 1e-12
    assert abs(reconciled["pressure_pa"] - 101325.0) < 1e-12
    assert abs(reconciled["cp_j_kg_k"] - 4180.0) < 1e-12

    changed_fields = {change["field"] for change in changes}

    assert "temperature_in_k" in changed_fields
    assert "temperature_out_k" in changed_fields
    assert "pressure_pa" in changed_fields
    assert "cp_j_kg_k" in changed_fields


def test_reconcile_infers_calculate_mass_flow_mode():
    spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "material": "water",
        "flow_basis": "mass",
        "mass_flow_kg_s": 1.0,
        "cp_j_kg_k": 4184.0,
        "pressure_pa": 100000.0,
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0,
    }

    prompt = "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?"

    reconciled, changes = reconcile_spec_with_prompt(spec, prompt)

    assert reconciled["mode"] == "calculate_mass_flow"
    assert abs(reconciled["temperature_in_k"] - 298.15) < 1e-12
    assert abs(reconciled["temperature_out_k"] - 353.15) < 1e-12
    assert abs(reconciled["heat_duty_w"] - 100000.0) < 1e-12

    changed_fields = {change["field"] for change in changes}

    assert "mode" in changed_fields
    assert "heat_duty_w" in changed_fields
