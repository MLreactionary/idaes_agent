import json
import re
from pathlib import Path


def is_utility_optimization_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    return (
        ("minimize" in prompt_lower or "optimize" in prompt_lower)
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


def plan_utility_optimization_problem(prompt: str, trace_dir: Path | None = None) -> dict:
    spec = {
        "problem_type": "utility_emissions_optimization",
        "mode": "minimize_cost_with_emissions_cap",
        "optimization_solver": "glpk",
        "heat_demand_kwh": extract_heat_demand_kwh(prompt),
        "emissions_cap_kg_co2": extract_emissions_cap_kg_co2(prompt),
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
