import json
import math
from pathlib import Path

from app.registry import get_problem_type


class VerifierError(Exception):
    pass


def _check(name: str, passed: bool, message: str, details: dict | None = None) -> dict:
    return {
        "name": name,
        "passed": bool(passed),
        "message": message,
        "details": details or {}
    }


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def verify_result(parsed_result: dict, structured_spec: dict) -> dict:
    """
    Deterministically verify model execution results.

    The LLM does not decide whether this passed.
    This function decides based on registry rules and engineering equations.
    """

    checks = []

    problem_type = structured_spec.get("problem_type")
    if not problem_type:
        raise VerifierError("structured_spec is missing problem_type")

    problem_config = get_problem_type(problem_type)
    verifier_config = problem_config["verifier"]

    # 1. Required fields
    required_fields = verifier_config["required_result_fields"]
    missing_fields = [field for field in required_fields if field not in parsed_result]

    checks.append(
        _check(
            name="required_result_fields",
            passed=len(missing_fields) == 0,
            message="All required RESULT_JSON fields are present."
            if not missing_fields
            else f"Missing required RESULT_JSON fields: {missing_fields}",
            details={"missing_fields": missing_fields}
        )
    )

    # If key fields are missing, continue where possible but final result will fail.

    # 2. Problem type matches
    result_problem_type = parsed_result.get("problem_type")
    checks.append(
        _check(
            name="problem_type_matches",
            passed=result_problem_type == problem_type,
            message=f"Result problem_type matches structured spec: {problem_type}"
            if result_problem_type == problem_type
            else f"Result problem_type {result_problem_type} does not match spec {problem_type}",
            details={
                "spec_problem_type": problem_type,
                "result_problem_type": result_problem_type
            }
        )
    )

    # 3. Mode matches
    spec_mode = structured_spec.get("mode")
    result_mode = parsed_result.get("mode")
    checks.append(
        _check(
            name="mode_matches",
            passed=result_mode == spec_mode,
            message=f"Result mode matches structured spec: {spec_mode}"
            if result_mode == spec_mode
            else f"Result mode {result_mode} does not match spec {spec_mode}",
            details={
                "spec_mode": spec_mode,
                "result_mode": result_mode
            }
        )
    )

    # 4. Solver status
    allowed_solver_statuses = verifier_config["allowed_solver_statuses"]
    solver_status = parsed_result.get("solver_status")
    checks.append(
        _check(
            name="solver_status",
            passed=solver_status in allowed_solver_statuses,
            message=f"Solver status is acceptable: {solver_status}"
            if solver_status in allowed_solver_statuses
            else f"Solver status is not acceptable: {solver_status}",
            details={
                "solver_status": solver_status,
                "allowed_solver_statuses": allowed_solver_statuses
            }
        )
    )

    # 5. Termination condition
    allowed_termination_conditions = verifier_config["allowed_termination_conditions"]
    termination_condition = parsed_result.get("termination_condition")
    checks.append(
        _check(
            name="termination_condition",
            passed=termination_condition in allowed_termination_conditions,
            message=f"Termination condition is acceptable: {termination_condition}"
            if termination_condition in allowed_termination_conditions
            else f"Termination condition is not acceptable: {termination_condition}",
            details={
                "termination_condition": termination_condition,
                "allowed_termination_conditions": allowed_termination_conditions
            }
        )
    )

    # 6. Numeric fields finite
    numeric_fields = [
        "mass_flow_kg_s",
        "cp_j_kg_k",
        "temperature_in_k",
        "temperature_out_k",
        "heat_duty_w",
        "energy_balance_residual_w"
    ]

    non_finite_fields = [
        field for field in numeric_fields
        if field in parsed_result and not _is_finite_number(parsed_result[field])
    ]

    checks.append(
        _check(
            name="numeric_fields_finite",
            passed=len(non_finite_fields) == 0,
            message="All numeric result fields are finite."
            if not non_finite_fields
            else f"Non-finite numeric fields found: {non_finite_fields}",
            details={"non_finite_fields": non_finite_fields}
        )
    )

    # 7. Field ranges from registry
    field_ranges = problem_config.get("field_ranges", {})
    range_failures = []

    for field, bounds in field_ranges.items():
        if field not in parsed_result:
            continue

        value = parsed_result[field]
        if not _is_finite_number(value):
            continue

        min_value = bounds["min"]
        max_value = bounds["max"]

        if value < min_value or value > max_value:
            range_failures.append(
                {
                    "field": field,
                    "value": value,
                    "min": min_value,
                    "max": max_value
                }
            )

    checks.append(
        _check(
            name="field_ranges",
            passed=len(range_failures) == 0,
            message="All checked result fields are within registry ranges."
            if not range_failures
            else f"Some result fields are outside registry ranges: {range_failures}",
            details={"range_failures": range_failures}
        )
    )

    # 8. Energy balance equation
    energy_tol = float(verifier_config["energy_balance_abs_tolerance_w"])

    required_for_energy = [
        "mass_flow_kg_s",
        "cp_j_kg_k",
        "temperature_in_k",
        "temperature_out_k",
        "heat_duty_w"
    ]

    can_check_energy = all(
        field in parsed_result and _is_finite_number(parsed_result[field])
        for field in required_for_energy
    )

    if can_check_energy:
        m_dot = parsed_result["mass_flow_kg_s"]
        cp = parsed_result["cp_j_kg_k"]
        tin = parsed_result["temperature_in_k"]
        tout = parsed_result["temperature_out_k"]
        q_reported = parsed_result["heat_duty_w"]

        q_expected = m_dot * cp * (tout - tin)
        q_error = q_reported - q_expected

        checks.append(
            _check(
                name="energy_balance",
                passed=abs(q_error) <= energy_tol,
                message="Energy balance is satisfied."
                if abs(q_error) <= energy_tol
                else f"Energy balance error too large: {q_error} W",
                details={
                    "q_reported_w": q_reported,
                    "q_expected_w": q_expected,
                    "q_error_w": q_error,
                    "tolerance_w": energy_tol
                }
            )
        )
    else:
        checks.append(
            _check(
                name="energy_balance",
                passed=False,
                message="Cannot check energy balance because required numeric fields are missing or invalid.",
                details={"required_fields": required_for_energy}
            )
        )

    # 9. Reported residual
    residual = parsed_result.get("energy_balance_residual_w")

    if _is_finite_number(residual):
        checks.append(
            _check(
                name="reported_energy_residual",
                passed=abs(residual) <= energy_tol,
                message="Reported energy residual is within tolerance."
                if abs(residual) <= energy_tol
                else f"Reported energy residual too large: {residual} W",
                details={
                    "reported_residual_w": residual,
                    "tolerance_w": energy_tol
                }
            )
        )
    else:
        checks.append(
            _check(
                name="reported_energy_residual",
                passed=False,
                message="Reported energy residual is missing or not finite.",
                details={"reported_residual_w": residual}
            )
        )

    # 10. Thermal direction consistency
    heat_duty = parsed_result.get("heat_duty_w")
    thermal_direction = parsed_result.get("thermal_direction")

    if _is_finite_number(heat_duty):
        if heat_duty > 0:
            expected_direction = "heating"
        elif heat_duty < 0:
            expected_direction = "cooling"
        else:
            expected_direction = "no_temperature_change"

        checks.append(
            _check(
                name="thermal_direction",
                passed=thermal_direction == expected_direction,
                message=f"Thermal direction is consistent: {thermal_direction}"
                if thermal_direction == expected_direction
                else f"Thermal direction {thermal_direction} should be {expected_direction}",
                details={
                    "heat_duty_w": heat_duty,
                    "reported_direction": thermal_direction,
                    "expected_direction": expected_direction
                }
            )
        )
    else:
        checks.append(
            _check(
                name="thermal_direction",
                passed=False,
                message="Cannot check thermal direction because heat_duty_w is missing or invalid.",
                details={"heat_duty_w": heat_duty}
            )
        )

    verified = all(check["passed"] for check in checks)
    failures = [check for check in checks if not check["passed"]]

    return {
        "verified": verified,
        "problem_type": problem_type,
        "mode": spec_mode,
        "num_checks": len(checks),
        "num_failures": len(failures),
        "checks": checks,
        "failures": failures
    }


def write_verification(parsed_result_path: Path, structured_spec_path: Path, run_dir: Path) -> Path:
    parsed_result_path = Path(parsed_result_path)
    structured_spec_path = Path(structured_spec_path)
    run_dir = Path(run_dir)

    if not parsed_result_path.exists():
        raise VerifierError(f"parsed_result.json not found: {parsed_result_path}")

    if not structured_spec_path.exists():
        raise VerifierError(f"structured_spec.json not found: {structured_spec_path}")

    parsed_result = json.loads(parsed_result_path.read_text(encoding="utf-8"))
    structured_spec = json.loads(structured_spec_path.read_text(encoding="utf-8"))

    verification = verify_result(parsed_result, structured_spec)

    verification_path = run_dir / "verification.json"
    verification_path.write_text(
        json.dumps(verification, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    return verification_path


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    run_dir = project_root / "outputs" / "runs" / "codegen_test"

    parsed_result_path = run_dir / "parsed_result.json"
    structured_spec_path = run_dir / "structured_spec.json"

    verification_path = write_verification(
        parsed_result_path=parsed_result_path,
        structured_spec_path=structured_spec_path,
        run_dir=run_dir
    )

    print("Verification complete")
    print(f"verification_path: {verification_path}")
