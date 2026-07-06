from app.verifier import verify_result


def base_spec():
    return {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "material": "water",
        "flow_basis": "mass",
        "mass_flow_kg_s": 1.0,
        "cp_j_kg_k": 4184.0,
        "pressure_pa": 100000.0,
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0
    }


def base_result():
    return {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "backend": "pyomo",
        "solver_name": "direct_linear_energy_balance",
        "solver_status": "ok",
        "termination_condition": "optimal",
        "material": "water",
        "flow_basis": "mass",
        "mass_flow_kg_s": 1.0,
        "cp_j_kg_k": 4184.0,
        "pressure_pa": 100000.0,
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0,
        "heat_duty_w": 209200.0,
        "energy_balance_residual_w": 0.0,
        "thermal_direction": "heating"
    }


def test_valid_heating_result_passes():
    verification = verify_result(base_result(), base_spec())

    assert verification["verified"] is True
    assert verification["num_failures"] == 0


def test_bad_energy_balance_fails():
    result = base_result()
    result["heat_duty_w"] = 123.0

    verification = verify_result(result, base_spec())

    assert verification["verified"] is False
    assert any(
        failure["name"] == "energy_balance"
        for failure in verification["failures"]
    )


def test_bad_solver_status_fails():
    result = base_result()
    result["solver_status"] = "error"

    verification = verify_result(result, base_spec())

    assert verification["verified"] is False
    assert any(
        failure["name"] == "solver_status"
        for failure in verification["failures"]
    )


def test_bad_thermal_direction_fails():
    result = base_result()
    result["thermal_direction"] = "cooling"

    verification = verify_result(result, base_spec())

    assert verification["verified"] is False
    assert any(
        failure["name"] == "thermal_direction"
        for failure in verification["failures"]
    )
