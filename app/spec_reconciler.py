import re
from copy import deepcopy


def _to_float(value: str) -> float:
    return float(value.strip())


def extract_temperatures_k(prompt: str) -> list[float]:
    """
    Extract temperatures from the prompt and convert to Kelvin.

    Supports:
    - 300 K
    - 27 C
    - 27 °C

    Returns temperatures in the order they appear.
    """
    pattern = re.compile(
        r"(-?\d+(?:\.\d+)?)\s*(?:°\s*)?(K|C)\b",
        flags=re.IGNORECASE
    )

    temps = []

    for match in pattern.finditer(prompt):
        value = _to_float(match.group(1))
        unit = match.group(2).upper()

        if unit == "K":
            temps.append(value)
        elif unit == "C":
            temps.append(value + 273.15)

    return temps


def extract_mass_flow_kg_s(prompt: str) -> float | None:
    """
    Extract mass flow like:
    - 2 kg/s
    - 2 kg / s
    """
    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*kg\s*/\s*s\b",
        prompt,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    return _to_float(match.group(1))


def extract_pressure_pa(prompt: str) -> float | None:
    """
    Extract pressure from:
    - 1 bar
    - 100000 Pa
    """
    bar_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*bar\b",
        prompt,
        flags=re.IGNORECASE
    )

    if bar_match:
        return _to_float(bar_match.group(1)) * 100000.0

    pa_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*Pa\b",
        prompt,
        flags=re.IGNORECASE
    )

    if pa_match:
        return _to_float(pa_match.group(1))

    return None


def extract_heat_duty_w(prompt: str) -> float | None:
    """
    Extract heat duty from:
    - 100 kW
    - 2 MW
    - 50000 W

    Uses sign from language:
    - removed / cooled / cooling / rejects => negative
    - receives / added / heat it / heated => positive
    """
    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*(MW|kW|W)\b",
        prompt,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    value = _to_float(match.group(1))
    unit = match.group(2).lower()

    if unit == "mw":
        value_w = value * 1_000_000.0
    elif unit == "kw":
        value_w = value * 1000.0
    else:
        value_w = value

    prompt_lower = prompt.lower()

    negative_markers = [
        "removed",
        "remove",
        "cool",
        "cooled",
        "cooling",
        "reject",
        "rejected"
    ]

    positive_markers = [
        "receives",
        "receive",
        "added",
        "add",
        "heated",
        "heat it",
        "supplied",
        "supply"
    ]

    if any(marker in prompt_lower for marker in negative_markers):
        return -abs(value_w)

    if any(marker in prompt_lower for marker in positive_markers):
        return abs(value_w)

    return value_w


def reconcile_spec_with_prompt(spec: dict, prompt: str) -> tuple[dict, list[dict]]:
    """
    Reconcile LLM-generated spec with explicit numerical quantities in prompt.

    This protects against LLM numeric copying/conversion mistakes.
    The LLM still decides problem type and mode, but explicit quantities are
    deterministically checked and overwritten when confidently parsed.
    """
    reconciled = deepcopy(spec)
    changes = []

    mode = reconciled.get("mode")

    temps_k = extract_temperatures_k(prompt)
    mass_flow = extract_mass_flow_kg_s(prompt)
    pressure = extract_pressure_pa(prompt)
    heat_duty = extract_heat_duty_w(prompt)

    def set_field(field: str, value):
        old_value = reconciled.get(field)
        if old_value != value:
            changes.append(
                {
                    "field": field,
                    "old_value": old_value,
                    "new_value": value,
                    "reason": "Explicitly parsed from original prompt."
                }
            )
            reconciled[field] = value

    if mode == "calculate_heat_duty":
        if len(temps_k) >= 2:
            set_field("temperature_in_k", temps_k[0])
            set_field("temperature_out_k", temps_k[1])

    elif mode == "calculate_outlet_temperature":
        if len(temps_k) >= 1:
            set_field("temperature_in_k", temps_k[0])
        if heat_duty is not None:
            set_field("heat_duty_w", heat_duty)

    if mass_flow is not None:
        set_field("mass_flow_kg_s", mass_flow)

    if pressure is not None:
        set_field("pressure_pa", pressure)

    return reconciled, changes


if __name__ == "__main__":
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

    print("reconciled:")
    print(reconciled)
    print("changes:")
    print(changes)
