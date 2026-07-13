import json
import re
from pathlib import Path


def is_utility_optimization_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    return (
        ("minimize" in prompt_lower or "optimize" in prompt_lower or "sweep" in prompt_lower or "tradeoff" in prompt_lower)
        and ("heat" in prompt_lower or "utility" in prompt_lower)
        and ("cost" in prompt_lower)
        and ("emissions" in prompt_lower or "co2" in prompt_lower)
    )


def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def extract_heat_demand_kwh(prompt: str) -> float:
    heat_match = re.search(
        r"needs\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*kW",
        prompt,
        flags=re.IGNORECASE
    )

    if not heat_match:
        raise ValueError("Could not extract heat demand in kW.")

    heat_kw = _to_float(heat_match.group(1))

    duration_match = re.search(
        r"for\s+([-+]?\d+(?:\.\d+)?)\s*(?:hr|hour|hours)",
        prompt,
        flags=re.IGNORECASE
    )

    duration_hr = _to_float(duration_match.group(1)) if duration_match else 1.0

    return heat_kw * duration_hr


def extract_utilities(prompt: str) -> list[dict]:
    pattern = re.compile(
        r"([A-Za-z][A-Za-z0-9_\s]*?)\s+cost\s+([-+]?\d+(?:\.\d+)?)\s*\$?\s*/\s*kWh"
        r"\s+emissions\s+([-+]?\d+(?:\.\d+)?)\s*kg\s*CO2\s*/\s*kWh",
        flags=re.IGNORECASE
    )

    utilities = []

    for match in pattern.finditer(prompt):
        raw_name = match.group(1).strip()
        name = raw_name.lower().replace("and ", "").strip().replace(" ", "_")

        utilities.append(
            {
                "name": name,
                "cost_per_kwh": _to_float(match.group(2)),
                "emissions_kg_co2_per_kwh": _to_float(match.group(3))
            }
        )

    if len(utilities) < 2:
        raise ValueError(f"Expected at least two utilities, found {len(utilities)}.")

    return utilities


def extract_emissions_cap_kg_co2(prompt: str) -> float:
    patterns = [
        r"emissions\s+must\s+be\s+(?:at\s+most|below|under|<=|less\s+than)\s+([-+]?\d+(?:\.\d+)?)\s*kg\s*CO2",
        r"emissions\s+(?:cap|limit|maximum|max)\s+([-+]?\d+(?:\.\d+)?)\s*kg\s*CO2",
    ]

    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            return _to_float(match.group(1))

    raise ValueError("Could not extract emissions cap in kg CO2.")




def extract_period_heat_demands_kwh(prompt: str):
    pattern = re.compile(
        r"period\s+([A-Za-z0-9_]+)\s+needs\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*kW"
        r"(?:\s+of\s+heat)?(?:\s+for\s+([-+]?\d+(?:\.\d+)?)\s*(?:hr|hour|hours))?",
        flags=re.IGNORECASE
    )

    periods = []

    for match in pattern.finditer(prompt):
        period_name = "period_" + match.group(1).lower()
        heat_kw = _to_float(match.group(2))
        duration_hr = _to_float(match.group(3)) if match.group(3) is not None else 1.0

        periods.append(
            {
                "name": period_name,
                "heat_demand_kwh": heat_kw * duration_hr
            }
        )

    return periods


def extract_total_emissions_cap_kg_co2(prompt: str) -> float:
    patterns = [
        r"total\s+emissions\s+must\s+be\s+(?:at\s+most|below|under|<=|less\s+than)\s+([-+]?\d+(?:\.\d+)?)\s*kg\s*CO2",
        r"total\s+emissions\s+(?:cap|limit|maximum|max)\s+([-+]?\d+(?:\.\d+)?)\s*kg\s*CO2",
    ]

    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            return _to_float(match.group(1))

    raise ValueError("Could not extract total emissions cap in kg CO2.")


def extract_power_demand_kwh(prompt: str) -> float | None:
    patterns = [
        r"demand\s+of\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:kilowatts|kw)",
        r"meet\s+(?:a\s+)?(?:fixed\s+)?(?:community\s+)?demand\s+of\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:kilowatts|kw)",
        r"needs\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:kilowatts|kw)\s+of\s+power",
    ]

    demand_kw = None

    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            demand_kw = _to_float(match.group(1))
            break

    if demand_kw is None:
        return None

    duration_match = re.search(
        r"for\s+([-+]?\d+(?:\.\d+)?)\s*(?:hr|hour|hours)",
        prompt,
        flags=re.IGNORECASE
    )

    duration_hr = _to_float(duration_match.group(1)) if duration_match else 1.0
    return demand_kw * duration_hr


def _split_compact_cost_emissions(value: str) -> tuple[float, float]:
    cleaned = value.replace("$", "").strip()

    if "." in cleaned:
        before, after = cleaned.split(".", 1)

        if len(before) >= 3:
            cost = float(before[:-1])
            emissions = float(before[-1] + "." + after)
            return cost, emissions

        return float(cleaned), 0.0

    if len(cleaned) >= 2:
        return float(cleaned[:-1]), float(cleaned[-1])

    return float(cleaned), 0.0


def _split_compact_min_max(value: str) -> tuple[float, float]:
    cleaned = value.replace(",", "").strip()

    if len(cleaned) >= 5:
        return float(cleaned[:-3]), float(cleaned[-3:])

    if len(cleaned) >= 4:
        return float(cleaned[:-2]), float(cleaned[-2:])

    raise ValueError("Could not split compact min/max value: " + value)


def extract_power_plants(prompt: str) -> list[dict]:
    clean_prompt = prompt.replace("\n", " ")

    known_names = [
        "Coal Plant",
        "Gas Plant",
        "Biomass Plant",
        "Solar Plant",
        "Wind Plant",
    ]

    positions = []

    for name in known_names:
        match = re.search(re.escape(name), clean_prompt, flags=re.IGNORECASE)
        if match:
            positions.append((match.start(), match.end(), name))

    positions.sort()

    plants = []

    for idx, (_, end, name) in enumerate(positions):
        next_start = positions[idx + 1][0] if idx + 1 < len(positions) else len(clean_prompt)
        segment = clean_prompt[end:next_start]

        min_match = re.search(
            r"min\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:kw|kwh)?",
            segment,
            flags=re.IGNORECASE
        )
        max_match = re.search(
            r"max\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*(?:kw|kwh)?",
            segment,
            flags=re.IGNORECASE
        )
        cost_match = re.search(
            r"cost\s+\$?([-+]?\d+(?:,\d{3})*(?:\.\d+)?)",
            segment,
            flags=re.IGNORECASE
        )
        emissions_match = re.search(
            r"emissions\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)",
            segment,
            flags=re.IGNORECASE
        )

        if min_match and max_match and cost_match and emissions_match:
            min_output = _to_float(min_match.group(1))
            max_output = _to_float(max_match.group(1))
            cost = _to_float(cost_match.group(1))
            emissions = _to_float(emissions_match.group(1))
        else:
            numbers = re.findall(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", segment)

            if len(numbers) >= 4:
                min_output = _to_float(numbers[0])
                max_output = _to_float(numbers[1])
                cost = _to_float(numbers[2])
                emissions = _to_float(numbers[3])
            elif len(numbers) >= 2:
                min_output, max_output = _split_compact_min_max(numbers[0])
                cost, emissions = _split_compact_cost_emissions(numbers[1])
            else:
                continue

        plants.append(
            {
                "name": name.lower().replace(" ", "_"),
                "min_output_kwh": min_output,
                "max_output_kwh": max_output,
                "cost_per_kwh": cost,
                "emissions_per_kwh": emissions,
            }
        )

    return plants


def extract_emissions_cap_sweep_kg_co2(prompt: str):
    pattern = (
        r"sweep\s+emissions\s+caps?\s+from\s+([-+]?\d+(?:\.\d+)?)\s+"
        r"to\s+([-+]?\d+(?:\.\d+)?)\s*kg\s*CO2"
        r"(?:[^.]*?(?:step\s+|in\s+)([-+]?\d+(?:\.\d+)?)(?:\s*kg)?\s*steps?)?"
    )

    match = re.search(pattern, prompt, flags=re.IGNORECASE)

    if not match:
        return None

    start = _to_float(match.group(1))
    stop = _to_float(match.group(2))
    step = _to_float(match.group(3)) if match.group(3) is not None else 10.0

    if step <= 0:
        raise ValueError("Emissions cap sweep step must be positive.")

    values = []
    current = start

    while current <= stop + 1e-9:
        values.append(round(current, 10))
        current += step

    if not values:
        raise ValueError("Could not build emissions cap sweep values.")

    return values

def plan_utility_optimization_problem(prompt: str, trace_dir: Path | None = None) -> dict:
    periods = extract_period_heat_demands_kwh(prompt)
    sweep_values = extract_emissions_cap_sweep_kg_co2(prompt)
    power_demand_kwh = extract_power_demand_kwh(prompt)
    power_plants = extract_power_plants(prompt)

    if power_demand_kwh is not None and len(power_plants) >= 2:
        spec = {
            "problem_type": "utility_emissions_optimization",
            "mode": "power_dispatch_minimize_cost",
            "optimization_solver": "glpk",
            "power_demand_kwh": power_demand_kwh,
            "plants": power_plants,
        }

        try:
            spec["emissions_cap_kg_co2"] = extract_emissions_cap_kg_co2(prompt)
        except ValueError:
            pass

    elif len(periods) >= 2:
        spec = {
            "problem_type": "utility_emissions_optimization",
            "mode": "multi_period_minimize_cost_with_emissions_cap",
            "optimization_solver": "glpk",
            "periods": periods,
            "total_emissions_cap_kg_co2": extract_total_emissions_cap_kg_co2(prompt),
            "utilities": extract_utilities(prompt),
        }
    elif sweep_values is None:
        spec = {
            "problem_type": "utility_emissions_optimization",
            "mode": "minimize_cost_with_emissions_cap",
            "optimization_solver": "glpk",
            "heat_demand_kwh": extract_heat_demand_kwh(prompt),
            "emissions_cap_kg_co2": extract_emissions_cap_kg_co2(prompt),
            "utilities": extract_utilities(prompt),
        }
    else:
        spec = {
            "problem_type": "utility_emissions_optimization",
            "mode": "sweep_emissions_cap",
            "optimization_solver": "glpk",
            "heat_demand_kwh": extract_heat_demand_kwh(prompt),
            "emissions_cap_values_kg_co2": sweep_values,
            "utilities": extract_utilities(prompt),
        }

    if trace_dir is not None:
        trace_dir = Path(trace_dir)

        trace = {
            "planner": "deterministic_utility_optimizer_planner",
            "prompt": prompt,
            "validated_spec": spec
        }

        (trace_dir / "planner_trace.json").write_text(
            json.dumps(trace, indent=2, sort_keys=True),
            encoding="utf-8"
        )

        (trace_dir / "planner_validated_spec.json").write_text(
            json.dumps(spec, indent=2, sort_keys=True),
            encoding="utf-8"
        )

    return spec


if __name__ == "__main__":
    prompt = (
        "A process needs 500 kW of heat for 1 hr. "
        "Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, "
        "and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. "
        "Emissions must be at most 60 kg CO2/hr. Minimize cost."
    )

    print(json.dumps(plan_utility_optimization_problem(prompt), indent=2, sort_keys=True))
