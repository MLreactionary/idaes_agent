import json
import re
from pathlib import Path

from app.mixer_planner import extract_all_mass_flows_kg_s


def is_splitter_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    markers = [
        "split ",
        "splitter",
        "splitting",
        "outlet 1",
        "outlet1",
        "outlet 2",
        "outlet2"
    ]

    return any(marker in prompt_lower for marker in markers)


def extract_outlet1_split_fraction(prompt: str) -> float | None:
    prompt_lower = prompt.lower()

    percent_patterns = [
        r"([-+]?\d+(?:\.\d+)?)\s*%",
        r"([-+]?\d+(?:\.\d+)?)\s*percent"
    ]

    for pattern in percent_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            value = float(match.group(1))
            return value / 100.0

    fraction_patterns = [
        r"split\s+fraction\s+(?:of\s+)?([-+]?\d+(?:\.\d+)?)",
        r"fraction\s+(?:of\s+)?([-+]?\d+(?:\.\d+)?)",
        r"outlet\s*1\s+(?:gets|receives|has)?\s*([-+]?\d+(?:\.\d+)?)"
    ]

    for pattern in fraction_patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            value = float(match.group(1))
            if 0.0 <= value <= 1.0:
                return value

    return None


def plan_splitter_problem(prompt: str, trace_dir: Path | None = None) -> dict:
    mass_flows = extract_all_mass_flows_kg_s(prompt)

    if len(mass_flows) < 1:
        raise ValueError("Splitter prompt must contain an inlet mass flow rate.")

    outlet1_split_fraction = extract_outlet1_split_fraction(prompt)

    if outlet1_split_fraction is None:
        raise ValueError("Splitter prompt must contain an outlet 1 split fraction or percentage.")

    if outlet1_split_fraction < 0.0 or outlet1_split_fraction > 1.0:
        raise ValueError("Outlet 1 split fraction must be between 0 and 1.")

    spec = {
        "problem_type": "splitter_mass_balance",
        "mode": "calculate_outlet_flows",
        "material": "water",
        "flow_basis": "mass",
        "inlet_mass_flow_kg_s": mass_flows[0],
        "outlet1_split_fraction": outlet1_split_fraction
    }

    if trace_dir is not None:
        trace_dir = Path(trace_dir)

        trace = {
            "planner": "deterministic_splitter_planner",
            "prompt": prompt,
            "extracted_mass_flows_kg_s": mass_flows,
            "extracted_outlet1_split_fraction": outlet1_split_fraction,
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
    prompt = "Split 10 kg/s of water with 30% going to outlet 1. What are the outlet flows?"
    print(json.dumps(plan_splitter_problem(prompt), indent=2, sort_keys=True))
