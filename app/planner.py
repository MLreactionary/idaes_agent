import re


class PlannerError(Exception):
    pass


def _parse_first_two_temperatures_k(prompt: str) -> tuple[float, float]:
    matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*K\b", prompt, flags=re.IGNORECASE)

    if len(matches) < 2:
        raise PlannerError(
            "Could not find two temperatures in K. "
            "For MVP, use wording like: from 300 K to 350 K."
        )

    return float(matches[0]), float(matches[1])


def _parse_pressure_pa(prompt: str) -> float | None:
    bar_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*bar\b",
        prompt,
        flags=re.IGNORECASE
    )
    if bar_match:
        return float(bar_match.group(1)) * 100000.0

    pa_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*Pa\b",
        prompt,
        flags=re.IGNORECASE
    )
    if pa_match:
        return float(pa_match.group(1))

    return None


def _parse_mass_flow_kg_s(prompt: str) -> float | None:
    match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*kg\s*/\s*s\b",
        prompt,
        flags=re.IGNORECASE
    )
    if match:
        return float(match.group(1))

    return None


def plan_problem(prompt: str) -> dict:
    """
    Temporary deterministic MVP planner.

    This is only for bootstrapping the full pipeline.
    Later we replace this with the real LLM planner.
    """
    normalized = prompt.lower()

    mentions_heater_family = any(
        word in normalized
        for word in ["heat", "heater", "cool", "cooler", "cooling"]
    )

    if not mentions_heater_family:
        raise PlannerError(
            "Unsupported prompt for MVP. "
            "Only heater/cooler sensible heat-balance prompts are supported."
        )

    temperature_in_k, temperature_out_k = _parse_first_two_temperatures_k(prompt)

    spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "temperature_in_k": temperature_in_k,
        "temperature_out_k": temperature_out_k
    }

    pressure_pa = _parse_pressure_pa(prompt)
    if pressure_pa is not None:
        spec["pressure_pa"] = pressure_pa

    mass_flow_kg_s = _parse_mass_flow_kg_s(prompt)
    if mass_flow_kg_s is not None:
        spec["mass_flow_kg_s"] = mass_flow_kg_s

    return spec


if __name__ == "__main__":
    demo_prompt = "Heat a water stream from 300 K to 350 K at 1 bar and report heat duty."
    print(plan_problem(demo_prompt))
