import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROBLEM_TYPES_PATH = PROJECT_ROOT / "configs" / "problem_types.json"


class RegistryError(Exception):
    pass


def load_problem_registry(path: Path = PROBLEM_TYPES_PATH) -> dict:
    if not path.exists():
        raise RegistryError(f"Problem registry not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if "problem_types" not in data:
        raise RegistryError("Registry must contain top-level key: problem_types")

    return data


def get_problem_type(problem_type: str) -> dict:
    registry = load_problem_registry()
    problem_types = registry["problem_types"]

    if problem_type not in problem_types:
        supported = sorted(problem_types.keys())
        raise RegistryError(
            f"Unsupported problem_type: {problem_type}. Supported: {supported}"
        )

    return problem_types[problem_type]


def apply_defaults(spec: dict) -> dict:
    if "problem_type" not in spec:
        raise RegistryError("Spec is missing required field: problem_type")

    problem_config = get_problem_type(spec["problem_type"])
    defaults = problem_config.get("defaults", {})

    merged = dict(defaults)
    merged.update(spec)

    return merged


def validate_spec(spec: dict) -> dict:
    """
    Deterministic validation of the structured problem spec.

    This does not call an LLM.
    This does not run a solver.
    This only checks whether the spec matches the supported registry contract.
    """
    spec = apply_defaults(spec)

    problem_type = spec["problem_type"]
    problem_config = get_problem_type(problem_type)

    mode = spec.get("mode")
    supported_modes = problem_config.get("supported_modes", [])

    if mode not in supported_modes:
        raise RegistryError(
            f"Unsupported mode for {problem_type}: {mode}. "
            f"Supported modes: {supported_modes}"
        )

    required_fields_by_mode = problem_config.get("required_fields_by_mode", {})
    required_fields = required_fields_by_mode.get(mode, [])

    missing = [field for field in required_fields if field not in spec]
    if missing:
        raise RegistryError(f"Spec is missing required fields: {missing}")

    field_ranges = problem_config.get("field_ranges", {})

    for field, bounds in field_ranges.items():
        if field not in spec:
            continue

        value = spec[field]

        if not isinstance(value, (int, float)):
            raise RegistryError(f"Field {field} must be numeric. Got: {value}")

        min_value = bounds["min"]
        max_value = bounds["max"]

        if value < min_value or value > max_value:
            raise RegistryError(
                f"Field {field}={value} outside valid range "
                f"[{min_value}, {max_value}]"
            )

    return spec


if __name__ == "__main__":
    demo_spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0
    }

    validated = validate_spec(demo_spec)
    print(json.dumps(validated, indent=2))
