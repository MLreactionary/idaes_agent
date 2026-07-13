import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "problem_types.json"


def get_problem_config(problem_type: str) -> dict:
    data = load_json(CONFIG_PATH)

    if "problem_types" in data and problem_type in data["problem_types"]:
        return data["problem_types"][problem_type]

    if problem_type in data:
        return data[problem_type]

    raise KeyError(f"Unknown problem_type in registry: {problem_type}")




def load_json(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_check(name: str, passed: bool, message: str) -> dict:
    return {
        "name": name,
        "passed": bool(passed),
        "message": message
    }


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _check_required_fields(result: dict, required_fields: list[str]) -> dict:
    missing = [field for field in required_fields if field not in result]

    if missing:
        return make_check(
            "required_result_fields",
            False,
            f"Missing required RESULT_JSON fields: {missing}"
        )

    return make_check(
        "required_result_fields",
        True,
        "All required RESULT_JSON fields are present."
    )


def _check_problem_type(result: dict, spec: dict) -> dict:
    passed = result.get("problem_type") == spec.get("problem_type")

    return make_check(
        "problem_type_matches",
        passed,
        (
            f"Result problem_type matches structured spec: {spec.get('problem_type')}"
            if passed
            else f"Expected problem_type {spec.get('problem_type')}, got {result.get('problem_type')}"
        )
    )


def _check_mode(result: dict, spec: dict) -> dict:
    passed = result.get("mode") == spec.get("mode")

    return make_check(
        "mode_matches",
        passed,
        (
            f"Result mode matches structured spec: {spec.get('mode')}"
            if passed
            else f"Expected mode {spec.get('mode')}, got {result.get('mode')}"
        )
    )


def _check_solver_status(result: dict, allowed_statuses: list[str]) -> dict:
    solver_status = result.get("solver_status")
    passed = solver_status in allowed_statuses

    return make_check(
        "solver_status",
        passed,
        (
            f"Solver status is acceptable: {solver_status}"
            if passed
            else f"Solver status is not acceptable: {solver_status}"
        )
    )


def _check_termination_condition(result: dict, allowed_conditions: list[str]) -> dict:
    termination_condition = result.get("termination_condition")
    passed = termination_condition in allowed_conditions

    return make_check(
        "termination_condition",
        passed,
        (
            f"Termination condition is acceptable: {termination_condition}"
            if passed
            else f"Termination condition is not acceptable: {termination_condition}"
        )
    )


def _check_numeric_fields_finite(result: dict) -> dict:
    numeric_fields = [
        key for key, value in result.items()
        if isinstance(value, (int, float))
    ]

    bad_fields = [
        key for key in numeric_fields
        if not _is_finite_number(result[key])
    ]

    if bad_fields:
        return make_check(
            "numeric_fields_finite",
            False,
            f"Numeric fields are not finite: {bad_fields}"
        )

    return make_check(
        "numeric_fields_finite",
        True,
        "All numeric result fields are finite."
    )


def _check_field_ranges(result: dict, field_ranges: dict) -> dict:
    failures = []

    for field, range_info in field_ranges.items():
        if field not in result:
            continue

        value = result[field]

        if not isinstance(value, (int, float)):
            continue

        min_value = range_info.get("min")
        max_value = range_info.get("max")

        if min_value is not None and value < min_value:
            failures.append(f"{field}={value} below min {min_value}")

        if max_value is not None and value > max_value:
            failures.append(f"{field}={value} above max {max_value}")

    if failures:
        return make_check(
            "field_ranges",
            False,
            "; ".join(failures)
        )

    return make_check(
        "field_ranges",
        True,
        "All checked result fields are within registry ranges."
    )


def _heater_energy_residual(result: dict) -> float:
    return (
        float(result["heat_duty_w"])
        - float(result["mass_flow_kg_s"])
        * float(result["cp_j_kg_k"])
        * (float(result["temperature_out_k"]) - float(result["temperature_in_k"]))
    )


def _mixer_energy_residual(result: dict) -> float:
    return (
        float(result["stream1_mass_flow_kg_s"])
        * float(result["stream1_cp_j_kg_k"])
        * (float(result["stream1_temperature_k"]) - float(result["outlet_temperature_k"]))
        + float(result["stream2_mass_flow_kg_s"])
        * float(result["stream2_cp_j_kg_k"])
        * (float(result["stream2_temperature_k"]) - float(result["outlet_temperature_k"]))
    )

def _splitter_mass_residual(result: dict) -> float:
    return (
        float(result["inlet_mass_flow_kg_s"])
        - float(result["outlet1_mass_flow_kg_s"])
        - float(result["outlet2_mass_flow_kg_s"])
    )


def _blend_mass_residual(result: dict) -> float:
    return (
        float(result["product_mass_kg"])
        - float(result["source1_mass_kg"])
        - float(result["source2_mass_kg"])
    )


def _blend_cost_residual(result: dict) -> float:
    expected_cost = (
        float(result["source1_cost_per_kg"]) * float(result["source1_mass_kg"])
        + float(result["source2_cost_per_kg"]) * float(result["source2_mass_kg"])
    )

    return float(result["total_cost"]) - expected_cost


def _blend_impurity_violation(result: dict) -> float:
    return (
        float(result["final_impurity_fraction"])
        - float(result["impurity_limit_fraction"])
    )



def _check_energy_balance(result: dict, tolerance: float) -> dict:
    problem_type = result.get("problem_type")

    try:
        if problem_type == "heater_energy_balance":
            residual = _heater_energy_residual(result)
            check_name = "energy_balance"
            success_message = "Energy balance is satisfied."
            failure_label = "Energy balance"

        elif problem_type == "adiabatic_mixer":
            residual = _mixer_energy_residual(result)
            check_name = "energy_balance"
            success_message = "Energy balance is satisfied."
            failure_label = "Energy balance"

        elif problem_type == "splitter_mass_balance":
            residual = _splitter_mass_residual(result)
            check_name = "mass_balance"
            success_message = "Mass balance is satisfied."
            failure_label = "Mass balance"

        elif problem_type == "blend_cost_optimization":
            residual = _blend_mass_residual(result)
            check_name = "optimization_mass_balance"
            success_message = "Optimization product mass balance is satisfied."
            failure_label = "Optimization mass balance"

        elif problem_type == "general_blend_cost_optimization":
            residual = float(result["product_mass_kg"]) - float(result["total_mass_kg"])
            check_name = "optimization_mass_balance"
            success_message = "General blend product mass balance is satisfied."
            failure_label = "General blend mass balance"

        elif problem_type == "utility_emissions_optimization":
            if result.get("mode") == "power_dispatch_minimize_cost":
                residual = float(result["power_balance_residual_kwh"])
                check_name = "optimization_power_dispatch_balance"
                success_message = "Power dispatch demand balance is satisfied."
                failure_label = "Power dispatch balance"
            elif result.get("mode") == "sweep_emissions_cap":
                residual = float(result["maximum_heat_balance_residual_kwh"])
                check_name = "optimization_sweep_heat_balance"
                success_message = "Utility sweep heat demand balances are satisfied."
                failure_label = "Utility sweep heat balance"
            elif result.get("mode") == "multi_period_minimize_cost_with_emissions_cap":
                residual = float(result["maximum_period_heat_balance_residual_kwh"])
                check_name = "optimization_multi_period_heat_balance"
                success_message = "Utility multi-period heat demand balances are satisfied."
                failure_label = "Utility multi-period heat balance"
            else:
                residual = float(result["heat_demand_kwh"]) - float(result["total_heat_kwh"])
                check_name = "optimization_heat_balance"
                success_message = "Utility heat demand balance is satisfied."
                failure_label = "Utility heat balance"

        else:
            return make_check(
                "balance",
                False,
                f"No balance verifier implemented for problem_type={problem_type}"
            )

    except KeyError as exc:
        return make_check(
            "balance",
            False,
            f"Missing field for balance check: {exc}"
        )

    passed = abs(residual) <= tolerance

    return make_check(
        check_name,
        passed,
        (
            success_message
            if passed
            else f"{failure_label} residual {residual} exceeds tolerance {tolerance}."
        )
    )


def _check_reported_energy_residual(result: dict, tolerance: float) -> dict:
    problem_type = result.get("problem_type")

    if problem_type == "splitter_mass_balance":
        residual = result.get("mass_balance_residual_kg_s")

        if residual is None:
            return make_check(
                "reported_mass_residual",
                False,
                "Missing reported mass_balance_residual_kg_s."
            )

        passed = abs(float(residual)) <= tolerance

        return make_check(
            "reported_mass_residual",
            passed,
            (
                "Reported mass residual is within tolerance."
                if passed
                else f"Reported mass residual {residual} exceeds tolerance {tolerance}."
            )
        )

    if problem_type == "utility_emissions_optimization":
        if result.get("mode") == "power_dispatch_minimize_cost":
            failures = []

            power_residual = abs(float(result.get("power_balance_residual_kwh", 0.0)))
            if power_residual > tolerance:
                failures.append(
                    f"Power dispatch residual {power_residual} exceeds tolerance {tolerance}."
                )

            emissions_violation = float(result.get("emissions_violation_kg_co2", 0.0))
            if emissions_violation > tolerance:
                failures.append(
                    f"Emissions violation {emissions_violation} exceeds tolerance {tolerance}."
                )

            passed = len(failures) == 0

            return make_check(
                "optimization_power_dispatch_result_consistency",
                passed,
                (
                    "Power dispatch satisfies demand and emissions checks."
                    if passed
                    else "; ".join(failures)
                )
            )

        if result.get("mode") == "multi_period_minimize_cost_with_emissions_cap":
            failures = []

            max_period_heat_residual = float(result.get("maximum_period_heat_balance_residual_kwh", 0.0))
            if max_period_heat_residual > tolerance:
                failures.append(
                    f"Maximum period heat residual {max_period_heat_residual} exceeds tolerance {tolerance}."
                )

            total_heat_residual = abs(float(result.get("total_heat_balance_residual_kwh", 0.0)))
            if total_heat_residual > tolerance:
                failures.append(
                    f"Total heat residual {total_heat_residual} exceeds tolerance {tolerance}."
                )

            emissions_violation = float(result.get("emissions_violation_kg_co2", 0.0))
            if emissions_violation > tolerance:
                failures.append(
                    f"Emissions violation {emissions_violation} exceeds tolerance {tolerance}."
                )

            passed = len(failures) == 0

            return make_check(
                "optimization_multi_period_result_consistency",
                passed,
                (
                    "Utility multi-period plan satisfies heat and emissions checks."
                    if passed
                    else "; ".join(failures)
                )
            )

        if result.get("mode") == "sweep_emissions_cap":
            failures = []

            max_heat_residual = float(result.get("maximum_heat_balance_residual_kwh", 0.0))
            if max_heat_residual > tolerance:
                failures.append(
                    f"Maximum sweep heat residual {max_heat_residual} exceeds tolerance {tolerance}."
                )

            max_emissions_violation = float(result.get("maximum_emissions_violation_kg_co2", 0.0))
            if max_emissions_violation > tolerance:
                failures.append(
                    f"Maximum sweep emissions violation {max_emissions_violation} exceeds tolerance {tolerance}."
                )

            for point in result.get("sweep_results", []):
                if point.get("sweep_point_status") != "optimal":
                    failures.append(
                        f"Sweep point at cap {point.get('emissions_cap_kg_co2')} is not optimal."
                    )

            passed = len(failures) == 0

            return make_check(
                "optimization_sweep_result_consistency",
                passed,
                (
                    "Utility emissions-cap sweep satisfies heat and emissions checks."
                    if passed
                    else "; ".join(failures)
                )
            )

        failures = []

        reported_heat_residual = result.get("heat_balance_residual_kwh")

        if reported_heat_residual is None:
            failures.append("Missing heat_balance_residual_kwh.")
        elif abs(float(reported_heat_residual)) > tolerance:
            failures.append(
                f"Reported heat residual {reported_heat_residual} exceeds tolerance {tolerance}."
            )

        try:
            expected_cost = sum(
                float(utility["cost_per_kwh"]) * float(utility["heat_kwh"])
                for utility in result["utility_results"]
            )
            cost_residual = float(result["total_cost"]) - expected_cost
            if abs(cost_residual) > tolerance:
                failures.append(
                    f"Total cost residual {cost_residual} exceeds tolerance {tolerance}."
                )
        except KeyError as exc:
            failures.append(f"Missing field for utility cost check: {exc}")

        try:
            expected_emissions = sum(
                float(utility["emissions_kg_co2_per_kwh"]) * float(utility["heat_kwh"])
                for utility in result["utility_results"]
            )
            emissions_residual = float(result["total_emissions_kg_co2"]) - expected_emissions
            if abs(emissions_residual) > tolerance:
                failures.append(
                    f"Total emissions residual {emissions_residual} exceeds tolerance {tolerance}."
                )

            violation = float(result["total_emissions_kg_co2"]) - float(result["emissions_cap_kg_co2"])
            if violation > tolerance:
                failures.append(
                    f"Emissions violation {violation} exceeds tolerance {tolerance}."
                )

            reported_violation = float(result.get("emissions_violation_kg_co2", 0.0))
            if reported_violation > tolerance:
                failures.append(
                    f"Reported emissions violation {reported_violation} exceeds tolerance {tolerance}."
                )
        except KeyError as exc:
            failures.append(f"Missing field for utility emissions check: {exc}")

        passed = len(failures) == 0

        return make_check(
            "optimization_result_consistency",
            passed,
            (
                "Utility optimization result satisfies heat, cost, and emissions checks."
                if passed
                else "; ".join(failures)
            )
        )

    if problem_type == "general_blend_cost_optimization":
        failures = []

        reported_mass_residual = result.get("mass_balance_residual_kg")

        if reported_mass_residual is None:
            failures.append("Missing mass_balance_residual_kg.")
        elif abs(float(reported_mass_residual)) > tolerance:
            failures.append(
                f"Reported mass residual {reported_mass_residual} exceeds tolerance {tolerance}."
            )

        try:
            expected_cost = sum(
                float(source["cost_per_kg"]) * float(source["mass_kg"])
                for source in result["source_results"]
            )
            cost_residual = float(result["total_cost"]) - expected_cost
            if abs(cost_residual) > tolerance:
                failures.append(
                    f"Total cost residual {cost_residual} exceeds tolerance {tolerance}."
                )
        except KeyError as exc:
            failures.append(f"Missing field for general blend cost check: {exc}")

        try:
            limits = result["quality_limits"]
            quality_results = result["quality_results"]

            for quality_name, limit in limits.items():
                value = float(quality_results[quality_name])
                violation = value - float(limit)

                if violation > tolerance:
                    failures.append(
                        f"Quality {quality_name} violation {violation} exceeds tolerance {tolerance}."
                    )

            max_violation = float(result.get("maximum_quality_violation_fraction", 0.0))
            if max_violation > tolerance:
                failures.append(
                    f"Maximum quality violation {max_violation} exceeds tolerance {tolerance}."
                )
        except KeyError as exc:
            failures.append(f"Missing field for general blend quality check: {exc}")

        try:
            max_availability_violation = float(result.get("maximum_source_availability_violation_kg", 0.0))
            if max_availability_violation > tolerance:
                failures.append(
                    f"Maximum source availability violation {max_availability_violation} kg exceeds tolerance {tolerance}."
                )

            for source in result["source_results"]:
                max_available = source.get("max_available_kg")
                if max_available is None:
                    continue

                violation = float(source["mass_kg"]) - float(max_available)
                if violation > tolerance:
                    failures.append(
                        f"Source {source.get('name')} availability violation {violation} kg exceeds tolerance {tolerance}."
                    )

                availability_slack = source.get("availability_slack_kg")
                if availability_slack is not None and float(availability_slack) < -tolerance:
                    failures.append(
                        f"Source {source.get('name')} availability slack {availability_slack} kg is below tolerance."
                    )
        except KeyError as exc:
            failures.append(f"Missing field for general blend availability check: {exc}")

        try:
            max_minimum_usage_violation = float(result.get("maximum_minimum_usage_violation_kg", 0.0))
            if max_minimum_usage_violation > tolerance:
                failures.append(
                    f"Maximum minimum usage violation {max_minimum_usage_violation} kg exceeds tolerance {tolerance}."
                )

            for source in result["source_results"]:
                min_required = source.get("min_required_kg")
                if min_required is None:
                    continue

                violation = float(min_required) - float(source["mass_kg"])
                if violation > tolerance:
                    failures.append(
                        f"Source {source.get('name')} minimum usage violation {violation} kg exceeds tolerance {tolerance}."
                    )

                minimum_usage_slack = source.get("minimum_usage_slack_kg")
                if minimum_usage_slack is not None and float(minimum_usage_slack) < -tolerance:
                    failures.append(
                        f"Source {source.get('name')} minimum usage slack {minimum_usage_slack} kg is below tolerance."
                    )
        except KeyError as exc:
            failures.append(f"Missing field for general blend minimum usage check: {exc}")

        passed = len(failures) == 0

        return make_check(
            "optimization_result_consistency",
            passed,
            (
                "General blend optimization result satisfies mass, cost, quality, availability, and minimum usage checks."
                if passed
                else "; ".join(failures)
            )
        )

    if problem_type == "blend_cost_optimization":
        failures = []

        reported_mass_residual = result.get("mass_balance_residual_kg")

        if reported_mass_residual is None:
            failures.append("Missing mass_balance_residual_kg.")
        elif abs(float(reported_mass_residual)) > tolerance:
            failures.append(
                f"Reported mass residual {reported_mass_residual} exceeds tolerance {tolerance}."
            )

        try:
            cost_residual = _blend_cost_residual(result)
            if abs(cost_residual) > tolerance:
                failures.append(
                    f"Total cost residual {cost_residual} exceeds tolerance {tolerance}."
                )
        except KeyError as exc:
            failures.append(f"Missing field for cost check: {exc}")

        try:
            impurity_violation = _blend_impurity_violation(result)
            if impurity_violation > tolerance:
                failures.append(
                    f"Impurity violation {impurity_violation} exceeds tolerance {tolerance}."
                )
        except KeyError as exc:
            failures.append(f"Missing field for impurity check: {exc}")

        passed = len(failures) == 0

        return make_check(
            "optimization_result_consistency",
            passed,
            (
                "Optimization result satisfies mass, cost, and impurity checks."
                if passed
                else "; ".join(failures)
            )
        )

    residual = result.get("energy_balance_residual_w")

    if residual is None:
        return make_check(
            "reported_energy_residual",
            False,
            "Missing reported energy_balance_residual_w."
        )

    passed = abs(float(residual)) <= tolerance

    return make_check(
        "reported_energy_residual",
        passed,
        (
            "Reported energy residual is within tolerance."
            if passed
            else f"Reported energy residual {residual} exceeds tolerance {tolerance}."
        )
    )


def _check_thermal_direction(result: dict) -> dict:
    problem_type = result.get("problem_type")

    if problem_type == "blend_cost_optimization":
        return make_check(
            "thermal_direction",
            True,
            "Thermal direction check skipped for blend cost optimization."
        )

    if problem_type == "general_blend_cost_optimization":
        return make_check(
            "thermal_direction",
            True,
            "Thermal direction check skipped for general blend cost optimization."
        )

    if problem_type == "utility_emissions_optimization":
        return make_check(
            "thermal_direction",
            True,
            "Thermal direction check skipped for utility emissions optimization."
        )

    if problem_type == "adiabatic_mixer":
        return make_check(
            "thermal_direction",
            True,
            "Thermal direction check skipped for adiabatic mixer."
        )

    if problem_type == "splitter_mass_balance":
        return make_check(
            "thermal_direction",
            True,
            "Thermal direction check skipped for splitter mass balance."
        )

    heat_duty = result.get("heat_duty_w")
    temperature_in = result.get("temperature_in_k")
    temperature_out = result.get("temperature_out_k")
    thermal_direction = result.get("thermal_direction")

    if heat_duty is None or temperature_in is None or temperature_out is None:
        return make_check(
            "thermal_direction",
            True,
            "Thermal direction check skipped because heat-duty fields are not present."
        )

    delta_t = float(temperature_out) - float(temperature_in)

    if abs(float(heat_duty)) < 1e-9 and abs(delta_t) < 1e-9:
        expected = "isothermal"
    elif float(heat_duty) > 0 and delta_t > 0:
        expected = "heating"
    elif float(heat_duty) < 0 and delta_t < 0:
        expected = "cooling"
    else:
        expected = "inconsistent"

    passed = thermal_direction == expected

    return make_check(
        "thermal_direction",
        passed,
        (
            f"Thermal direction is consistent: {thermal_direction}"
            if passed
            else f"Expected thermal_direction {expected}, got {thermal_direction}"
        )
    )


def verify_result(parsed_result: dict, structured_spec: dict) -> dict:
    problem_type = structured_spec["problem_type"]
    config = get_problem_config(problem_type)
    verifier_config = config.get("verifier", {})

    mode = structured_spec.get("mode")
    required_fields_by_mode = verifier_config.get("required_result_fields_by_mode", {})
    required_fields = required_fields_by_mode.get(mode, verifier_config.get("required_result_fields", []))
    allowed_solver_statuses = verifier_config.get("allowed_solver_statuses", ["ok"])
    allowed_termination_conditions = verifier_config.get("allowed_termination_conditions", ["optimal"])
    energy_tolerance = verifier_config.get("energy_balance_abs_tolerance_w", 1e-6)

    checks = [
        _check_required_fields(parsed_result, required_fields),
        _check_problem_type(parsed_result, structured_spec),
        _check_mode(parsed_result, structured_spec),
        _check_solver_status(parsed_result, allowed_solver_statuses),
        _check_termination_condition(parsed_result, allowed_termination_conditions),
        _check_numeric_fields_finite(parsed_result),
        _check_field_ranges(parsed_result, config.get("field_ranges", {})),
        _check_energy_balance(parsed_result, energy_tolerance),
        _check_reported_energy_residual(parsed_result, energy_tolerance),
        _check_thermal_direction(parsed_result),
    ]

    failures = [check for check in checks if not check["passed"]]
    num_failures = len(failures)

    return {
        "verified": num_failures == 0,
        "num_checks": len(checks),
        "num_failures": num_failures,
        "checks": checks,
        "failures": failures
    }


def write_verification(
    parsed_result_path: Path,
    structured_spec_path: Path,
    run_dir: Path
) -> Path:
    run_dir = Path(run_dir)

    parsed_result = load_json(parsed_result_path)
    structured_spec = load_json(structured_spec_path)

    verification = verify_result(parsed_result, structured_spec)

    verification_path = run_dir / "verification.json"
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    return verification_path


if __name__ == "__main__":
    raise SystemExit("Use write_verification() from the run pipeline.")
