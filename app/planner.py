import re


class PlannerError(Exception):
    pass


def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def _temperature_to_k(value: float, unit: str) -> float:
    unit_lower = unit.lower()

    if unit_lower == "k":
        return value

    if unit_lower in {"c", "degc", "°c"}:
        return value + 273.15

    raise PlannerError(f"Unsupported temperature unit: {unit}")


def _parse_temperatures_k(prompt: str) -> list[float]:
    matches = re.findall(
        r"(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*(K|C|degC|°C)\b",
        prompt,
        flags=re.IGNORECASE
    )

    return [
        _temperature_to_k(_to_float(value), unit)
        for value, unit in matches
    ]


def _parse_first_two_temperatures_k(prompt: str) -> tuple[float, float]:
    temperatures = _parse_temperatures_k(prompt)

    if len(temperatures) < 2:
        raise PlannerError(
            "Could not find two temperatures. "
            "Use wording like: from 300 K to 350 K or from 25 C to 80 C."
        )

    return temperatures[0], temperatures[1]


def _parse_first_temperature_k(prompt: str) -> float:
    temperatures = _parse_temperatures_k(prompt)

    if not temperatures:
        raise PlannerError(
            "Could not find an inlet temperature. "
            "Use wording like: water enters at 300 K."
        )

    return temperatures[0]


def _parse_pressure_pa(prompt: str) -> float | None:
    bar_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*bar\b",
        prompt,
        flags=re.IGNORECASE
    )
    if bar_match:
        return float(bar_match.group(1)) * 100000.0

    kpa_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*kPa\b",
        prompt,
        flags=re.IGNORECASE
    )
    if kpa_match:
        return float(kpa_match.group(1)) * 1000.0

    pa_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*Pa\b",
        prompt,
        flags=re.IGNORECASE
    )
    if pa_match:
        return float(pa_match.group(1))

    return None


def _parse_mass_flow_kg_s(prompt: str) -> float | None:
    kg_s_match = re.search(
        r"(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*kg\s*/\s*s\b",
        prompt,
        flags=re.IGNORECASE
    )
    if kg_s_match:
        return _to_float(kg_s_match.group(1))

    kg_hr_match = re.search(
        r"(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*kg\s*/\s*(?:hr|hour)\b",
        prompt,
        flags=re.IGNORECASE
    )
    if kg_hr_match:
        return _to_float(kg_hr_match.group(1)) / 3600.0

    return None


def _parse_cp_j_kg_k(prompt: str) -> float | None:
    kj_match = re.search(
        r"Cp\s*=\s*(-?\d+(?:\.\d+)?)\s*kJ\s*/\s*kg\s*/\s*K",
        prompt,
        flags=re.IGNORECASE
    )
    if kj_match:
        return float(kj_match.group(1)) * 1000.0

    j_match = re.search(
        r"Cp\s*=\s*(-?\d+(?:\.\d+)?)\s*J\s*/\s*kg\s*/\s*K",
        prompt,
        flags=re.IGNORECASE
    )
    if j_match:
        return float(j_match.group(1))

    return None


def _parse_heat_duty_w(prompt: str) -> float | None:
    match = re.search(
        r"(-?\d+(?:,\d{3})*(?:\.\d+)?)\s*kW\b",
        prompt,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    heat_duty_w = _to_float(match.group(1)) * 1000.0
    prompt_lower = prompt.lower()

    if "removed" in prompt_lower or "remove" in prompt_lower or "cool" in prompt_lower:
        return -abs(heat_duty_w)

    return heat_duty_w


def plan_problem(prompt: str) -> dict:
    """
    Deterministic heater/cooler sensible heat-balance planner.
    """
    normalized = prompt.lower()

    mentions_heater_family = any(
        word in normalized
        for word in ["heat", "heater", "cool", "cooler", "cooling", "temperature"]
    )

    if not mentions_heater_family:
        raise PlannerError(
            "Unsupported prompt for MVP. "
            "Only heater/cooler sensible heat-balance prompts are supported."
        )

    heat_duty_w = _parse_heat_duty_w(prompt)
    mass_flow_kg_s = _parse_mass_flow_kg_s(prompt)
    cp_j_kg_k = _parse_cp_j_kg_k(prompt)

    wants_mass_flow = "mass flow" in normalized or "flow rate" in normalized or "can i process" in normalized
    wants_outlet_temperature = (
        "outlet temperature" in normalized
        or "what is the outlet temperature" in normalized
        or ("enters at" in normalized and heat_duty_w is not None)
    )

    if wants_mass_flow:
        temperature_in_k, temperature_out_k = _parse_first_two_temperatures_k(prompt)
        if heat_duty_w is None:
            raise PlannerError("Could not find heat duty for mass-flow calculation.")

        spec = {
            "problem_type": "heater_energy_balance",
            "mode": "calculate_mass_flow",
            "temperature_in_k": temperature_in_k,
            "temperature_out_k": temperature_out_k,
            "heat_duty_w": heat_duty_w
        }

    elif wants_outlet_temperature:
        temperature_in_k = _parse_first_temperature_k(prompt)
        if heat_duty_w is None:
            raise PlannerError("Could not find heat duty for outlet-temperature calculation.")

        spec = {
            "problem_type": "heater_energy_balance",
            "mode": "calculate_outlet_temperature",
            "temperature_in_k": temperature_in_k,
            "heat_duty_w": heat_duty_w
        }

        if mass_flow_kg_s is not None:
            spec["mass_flow_kg_s"] = mass_flow_kg_s

    else:
        temperature_in_k, temperature_out_k = _parse_first_two_temperatures_k(prompt)

        spec = {
            "problem_type": "heater_energy_balance",
            "mode": "calculate_heat_duty",
            "temperature_in_k": temperature_in_k,
            "temperature_out_k": temperature_out_k
        }

        if mass_flow_kg_s is not None:
            spec["mass_flow_kg_s"] = mass_flow_kg_s

    pressure_pa = _parse_pressure_pa(prompt)
    if pressure_pa is not None:
        spec["pressure_pa"] = pressure_pa

    if cp_j_kg_k is not None:
        spec["cp_j_kg_k"] = cp_j_kg_k

    return spec


if __name__ == "__main__":
    demo_prompt = "Heat a water stream from 300 K to 350 K at 1 bar and report heat duty."
    print(plan_problem(demo_prompt))
