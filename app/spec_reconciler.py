import re
from copy import deepcopy


def _to_float(value: str) -> float:
    return float(value.replace(",", "").strip())


def _temperature_to_k(value: float, unit: str) -> float:
    unit = unit.lower().replace("°", "").strip()

    if unit in {"k", "kelvin"}:
        return value

    if unit in {"c", "degc", "celsius"}:
        return value + 273.15

    if unit in {"f", "degf", "fahrenheit"}:
        return (value - 32.0) * 5.0 / 9.0 + 273.15

    raise ValueError(f"Unsupported temperature unit: {unit}")


def _mass_flow_to_kg_s(value: float, unit: str) -> float:
    unit = unit.lower().strip()
    unit = unit.replace(" ", "")
    unit = unit.replace("per", "/")
    unit = unit.replace("hour", "hr")
    unit = unit.replace("hours", "hr")
    unit = unit.replace("minute", "min")
    unit = unit.replace("minutes", "min")
    unit = unit.replace("second", "s")
    unit = unit.replace("seconds", "s")

    if unit in {"kg/s", "kgs", "kg/sec"}:
        return value

    if unit in {"kg/hr", "kg/h"}:
        return value / 3600.0

    if unit in {"kg/min"}:
        return value / 60.0

    if unit in {"g/s", "gs", "g/sec"}:
        return value / 1000.0

    if unit in {"g/hr", "g/h"}:
        return value / 1000.0 / 3600.0

    if unit in {"g/min"}:
        return value / 1000.0 / 60.0

    raise ValueError(f"Unsupported mass flow unit: {unit}")


def _cp_to_j_kg_k(value: float, unit: str) -> float:
    unit = unit.lower().strip()
    unit = unit.replace(" ", "")
    unit = unit.replace("°", "")
    unit = unit.replace("per", "/")

    # Normalize common variants.
    unit = unit.replace("kg-k", "kg/k")
    unit = unit.replace("kg*k", "kg/k")
    unit = unit.replace("kg.k", "kg/k")
    unit = unit.replace("kgc", "kg/c")
    unit = unit.replace("kg-c", "kg/c")
    unit = unit.replace("kg*c", "kg/c")
    unit = unit.replace("kg.c", "kg/c")

    if unit in {
        "j/kg/k",
        "j/kg-k",
        "j/(kg*k)",
        "j/(kgk)",
        "j/kg/kelvin"
    }:
        return value

    if unit in {
        "kj/kg/k",
        "kj/kg-k",
        "kj/(kg*k)",
        "kj/(kgk)",
        "kj/kg/kelvin"
    }:
        return value * 1000.0

    if unit in {
        "j/kg/c",
        "j/kg-c",
        "j/(kg*c)",
        "j/(kgc)",
        "j/kg/celsius"
    }:
        return value

    if unit in {
        "kj/kg/c",
        "kj/kg-c",
        "kj/(kg*c)",
        "kj/(kgc)",
        "kj/kg/celsius"
    }:
        return value * 1000.0

    raise ValueError(f"Unsupported heat-capacity unit: {unit}")


def _pressure_to_pa(value: float, unit: str) -> float:
    unit = unit.lower().strip()

    if unit == "pa":
        return value

    if unit == "kpa":
        return value * 1000.0

    if unit == "mpa":
        return value * 1_000_000.0

    if unit == "bar":
        return value * 100000.0

    if unit == "atm":
        return value * 101325.0

    raise ValueError(f"Unsupported pressure unit: {unit}")


def _heat_duty_to_w(value: float, unit: str) -> float:
    unit = unit.lower().strip()
    unit = unit.replace(" ", "")

    if unit in {"w", "watt", "watts"}:
        return value

    if unit in {"kw", "kilowatt", "kilowatts", "kj/s"}:
        return value * 1000.0

    if unit in {"mw", "megawatt", "megawatts", "mj/s"}:
        return value * 1_000_000.0

    raise ValueError(f"Unsupported heat duty unit: {unit}")


def extract_temperatures_k(prompt: str) -> list[float]:
    """
    Extract temperatures in the order they appear.
    Supports K, C, F, Celsius, Fahrenheit.
    """
    pattern = re.compile(
        r"(?<![A-Za-z])"
        r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*(?:°\s*)?"
        r"(K|C|F|kelvin|celsius|fahrenheit)\b",
        flags=re.IGNORECASE
    )

    values = []

    for match in pattern.finditer(prompt):
        number = _to_float(match.group(1))
        unit = match.group(2)
        values.append(_temperature_to_k(number, unit))

    return values


def extract_mass_flow_kg_s(prompt: str) -> float | None:
    """
    Extract mass flow.
    Supports kg/s, kg/hr, kg/min, g/s, g/hr, g/min.
    """
    pattern = re.compile(
        r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*"
        r"(kg\s*/\s*s|kg\s*/\s*sec|kg\s*/\s*hr|kg\s*/\s*h|kg\s*/\s*min|"
        r"kg\s+per\s+second|kg\s+per\s+hour|kg\s+per\s+minute|"
        r"g\s*/\s*s|g\s*/\s*sec|g\s*/\s*hr|g\s*/\s*h|g\s*/\s*min|"
        r"g\s+per\s+second|g\s+per\s+hour|g\s+per\s+minute)"
        r"\b",
        flags=re.IGNORECASE
    )

    match = pattern.search(prompt)

    if not match:
        return None

    value = _to_float(match.group(1))
    unit = match.group(2)

    return _mass_flow_to_kg_s(value, unit)


def extract_cp_j_kg_k(prompt: str) -> float | None:
    """
    Extract heat capacity Cp.
    Supports J/kg/K, kJ/kg/K, J/kg-C, kJ/kg-C and common variants.
    """
    pattern = re.compile(
        r"(?:cp|heat\s*capacity|specific\s*heat)"
        r"\s*(?:=|is|of|:)?\s*"
        r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*"
        r"(kJ\s*/\s*kg\s*/\s*K|kJ\s*/\s*kg\s*[-*]\s*K|"
        r"J\s*/\s*kg\s*/\s*K|J\s*/\s*kg\s*[-*]\s*K|"
        r"kJ\s*/\s*kg\s*/\s*C|kJ\s*/\s*kg\s*[-*]\s*C|"
        r"J\s*/\s*kg\s*/\s*C|J\s*/\s*kg\s*[-*]\s*C)"
        r"\b",
        flags=re.IGNORECASE
    )

    match = pattern.search(prompt)

    if not match:
        return None

    value = _to_float(match.group(1))
    unit = match.group(2)

    return _cp_to_j_kg_k(value, unit)


def extract_pressure_pa(prompt: str) -> float | None:
    pattern = re.compile(
        r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*"
        r"(bar|atm|MPa|kPa|Pa)"
        r"\b",
        flags=re.IGNORECASE
    )

    match = pattern.search(prompt)

    if not match:
        return None

    value = _to_float(match.group(1))
    unit = match.group(2)

    return _pressure_to_pa(value, unit)


def extract_heat_duty_w(prompt: str) -> float | None:
    pattern = re.compile(
        r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*"
        r"(MW|kW|W|MJ\s*/\s*s|kJ\s*/\s*s)"
        r"\b",
        flags=re.IGNORECASE
    )

    match = pattern.search(prompt)

    if not match:
        return None

    value = _to_float(match.group(1))
    unit = match.group(2)

    heat_duty_w = _heat_duty_to_w(value, unit)

    prompt_lower = prompt.lower()

    negative_markers = [
        "removed",
        "remove",
        "cool",
        "cooled",
        "cooling",
        "reject",
        "rejected",
        "taken out",
        "take out"
    ]

    positive_markers = [
        "receives",
        "receive",
        "added",
        "add",
        "heated",
        "heat it",
        "supplied",
        "supply",
        "input"
    ]

    if any(marker in prompt_lower for marker in negative_markers):
        return -abs(heat_duty_w)

    if any(marker in prompt_lower for marker in positive_markers):
        return abs(heat_duty_w)

    return heat_duty_w



def prompt_requests_mass_flow(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    markers = [
        "mass flow",
        "flow rate",
        "required flow",
        "required mass",
        "what flow",
        "how much water",
        "how much material",
        "can i process",
        "can we process",
        "throughput",
        "kg/s can",
        "kg/hr can"
    ]

    return any(marker in prompt_lower for marker in markers)


def _record_change(changes: list[dict], field: str, old_value, new_value, reason: str):
    if old_value != new_value:
        changes.append(
            {
                "field": field,
                "old_value": old_value,
                "new_value": new_value,
                "reason": reason
            }
        )


def reconcile_spec_with_prompt(spec: dict, prompt: str) -> tuple[dict, list[dict]]:
    """
    LLM chooses problem type/mode.
    Deterministic reconciler corrects explicit numeric quantities from prompt.

    Returns:
        reconciled_spec, changes
    """
    reconciled = deepcopy(spec)
    changes = []

    temperatures_k = extract_temperatures_k(prompt)
    heat_duty_w_for_mode = extract_heat_duty_w(prompt)

    if (
        prompt_requests_mass_flow(prompt)
        and len(temperatures_k) >= 2
        and heat_duty_w_for_mode is not None
    ):
        old_value = reconciled.get("mode")
        new_value = "calculate_mass_flow"
        reconciled["mode"] = new_value
        _record_change(
            changes,
            "mode",
            old_value,
            new_value,
            "Prompt asks for mass flow and provides temperatures plus heat duty."
        )

    if len(temperatures_k) >= 1:
        old_value = reconciled.get("temperature_in_k")
        new_value = temperatures_k[0]
        reconciled["temperature_in_k"] = new_value
        _record_change(
            changes,
            "temperature_in_k",
            old_value,
            new_value,
            "Explicitly parsed from original prompt."
        )

    if len(temperatures_k) >= 2 and reconciled.get("mode") in {"calculate_heat_duty", "calculate_mass_flow"}:
        old_value = reconciled.get("temperature_out_k")
        new_value = temperatures_k[1]
        reconciled["temperature_out_k"] = new_value
        _record_change(
            changes,
            "temperature_out_k",
            old_value,
            new_value,
            "Explicitly parsed from original prompt."
        )

    # Older code below may also try to reconcile temperatures.
    # It is left harmless because _record_change only records real changes.

    if False and len(temperatures_k) >= 1 and "temperature_in_k" in reconciled:
        old_value = reconciled.get("temperature_in_k")
        new_value = temperatures_k[0]
        reconciled["temperature_in_k"] = new_value
        _record_change(
            changes,
            "temperature_in_k",
            old_value,
            new_value,
            "Explicitly parsed from original prompt."
        )

    if (
        len(temperatures_k) >= 2
        and reconciled.get("mode") == "calculate_heat_duty"
        and "temperature_out_k" in reconciled
    ):
        old_value = reconciled.get("temperature_out_k")
        new_value = temperatures_k[1]
        reconciled["temperature_out_k"] = new_value
        _record_change(
            changes,
            "temperature_out_k",
            old_value,
            new_value,
            "Explicitly parsed from original prompt."
        )

    mass_flow_kg_s = extract_mass_flow_kg_s(prompt)

    if mass_flow_kg_s is not None:
        old_value = reconciled.get("mass_flow_kg_s")
        reconciled["mass_flow_kg_s"] = mass_flow_kg_s
        _record_change(
            changes,
            "mass_flow_kg_s",
            old_value,
            mass_flow_kg_s,
            "Explicit mass-flow unit parsed and converted to kg/s."
        )

    cp_j_kg_k = extract_cp_j_kg_k(prompt)

    if cp_j_kg_k is not None:
        old_value = reconciled.get("cp_j_kg_k")
        reconciled["cp_j_kg_k"] = cp_j_kg_k
        _record_change(
            changes,
            "cp_j_kg_k",
            old_value,
            cp_j_kg_k,
            "Explicit heat capacity parsed and converted to J/kg/K."
        )

    pressure_pa = extract_pressure_pa(prompt)

    if pressure_pa is not None:
        old_value = reconciled.get("pressure_pa")
        reconciled["pressure_pa"] = pressure_pa
        _record_change(
            changes,
            "pressure_pa",
            old_value,
            pressure_pa,
            "Explicit pressure parsed and converted to Pa."
        )

    heat_duty_w = extract_heat_duty_w(prompt)

    if heat_duty_w is not None and reconciled.get("mode") in {"calculate_outlet_temperature", "calculate_mass_flow"}:
        old_value = reconciled.get("heat_duty_w")
        reconciled["heat_duty_w"] = heat_duty_w
        _record_change(
            changes,
            "heat_duty_w",
            old_value,
            heat_duty_w,
            "Explicit heat duty parsed and converted to W."
        )

    return reconciled, changes


if __name__ == "__main__":
    prompt = "Heat 3600 kg/hr of water from 25 C to 80 C using Cp = 4.18 kJ/kg/K."
    print("temperatures_k:", extract_temperatures_k(prompt))
    print("mass_flow_kg_s:", extract_mass_flow_kg_s(prompt))
    print("cp_j_kg_k:", extract_cp_j_kg_k(prompt))
