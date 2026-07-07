import json
import re
from pathlib import Path

from app.spec_reconciler import (
    _mass_flow_to_kg_s,
    _to_float,
    extract_temperatures_k,
    extract_cp_j_kg_k,
    extract_pressure_pa,
)


def is_mixer_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    markers = [
        "mix ",
        "mixed ",
        "mixer",
        "mixing",
        "combine ",
        "combined ",
        "blend ",
        "blended ",
        "blending",
        "merge ",
        "merged ",
        "merging"
    ]

    return any(marker in prompt_lower for marker in markers)


def extract_all_mass_flows_kg_s(prompt: str) -> list[float]:
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

    values = []

    for match in pattern.finditer(prompt):
        value = _to_float(match.group(1))
        unit = match.group(2)
        values.append(_mass_flow_to_kg_s(value, unit))

    return values


def plan_mixer_problem(prompt: str, trace_dir: Path | None = None) -> dict:
    mass_flows = extract_all_mass_flows_kg_s(prompt)
    temperatures = extract_temperatures_k(prompt)

    if len(mass_flows) < 2:
        raise ValueError("Mixer prompt must contain two inlet mass flow rates.")

    if len(temperatures) < 2:
        raise ValueError("Mixer prompt must contain two inlet temperatures.")

    cp = extract_cp_j_kg_k(prompt)
    pressure_pa = extract_pressure_pa(prompt)

    if cp is None:
        cp = 4184.0

    if pressure_pa is None:
        pressure_pa = 100000.0

    spec = {
        "problem_type": "adiabatic_mixer",
        "mode": "calculate_outlet_temperature",
        "material": "water",
        "flow_basis": "mass",
        "stream1_mass_flow_kg_s": mass_flows[0],
        "stream1_temperature_k": temperatures[0],
        "stream1_cp_j_kg_k": cp,
        "stream2_mass_flow_kg_s": mass_flows[1],
        "stream2_temperature_k": temperatures[1],
        "stream2_cp_j_kg_k": cp,
        "pressure_pa": pressure_pa
    }

    if trace_dir is not None:
        trace_dir = Path(trace_dir)
        trace = {
            "planner": "deterministic_mixer_planner",
            "prompt": prompt,
            "extracted_mass_flows_kg_s": mass_flows,
            "extracted_temperatures_k": temperatures,
            "extracted_cp_j_kg_k": cp,
            "extracted_pressure_pa": pressure_pa,
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
    prompt = "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?"
    print(json.dumps(plan_mixer_problem(prompt), indent=2, sort_keys=True))
