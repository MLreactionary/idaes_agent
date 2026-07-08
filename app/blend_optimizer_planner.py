import json
import re
from pathlib import Path


def is_blend_optimization_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    return (
        ("optimize" in prompt_lower or "minimize" in prompt_lower or "minimum cost" in prompt_lower)
        and ("blend" in prompt_lower or "source" in prompt_lower)
        and ("cost" in prompt_lower)
        and ("impurity" in prompt_lower)
    )


def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def _percent_to_fraction(value: float) -> float:
    return value / 100.0


def extract_product_mass_kg(prompt: str) -> float:
    patterns = [
        r"blend\s+of\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*kg",
        r"produce\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*kg",
        r"make\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*kg",
        r"([-+]?\d+(?:,\d{3})*(?:\.\d+)?)\s*kg\s+product",
    ]

    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            return _to_float(match.group(1))

    raise ValueError("Could not extract product mass in kg.")


def extract_sources(prompt: str) -> list[dict]:
    pattern = re.compile(
        r"source\s+([A-Za-z0-9_]+)"
        r"\s+cost\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*(?:\$|usd)?\s*/\s*kg"
        r"\s+impurity\s+([-+]?\d+(?:\.\d+)?)\s*%",
        flags=re.IGNORECASE
    )

    sources = []

    for match in pattern.finditer(prompt):
        sources.append(
            {
                "name": match.group(1),
                "cost_per_kg": _to_float(match.group(2)),
                "impurity_fraction": _percent_to_fraction(_to_float(match.group(3))),
            }
        )

    if len(sources) != 2:
        raise ValueError(
            f"Expected exactly two sources with cost and impurity, found {len(sources)}."
        )

    return sources


def extract_impurity_limit_fraction(prompt: str) -> float:
    patterns = [
        r"impurity\s+limit\s+([-+]?\d+(?:\.\d+)?)\s*%",
        r"final\s+impurity\s+limit\s+([-+]?\d+(?:\.\d+)?)\s*%",
        r"impurity\s+(?:at\s+most|below|under|<=|less\s+than)\s+([-+]?\d+(?:\.\d+)?)\s*%",
        r"with\s+.*?limit\s+([-+]?\d+(?:\.\d+)?)\s*%",
    ]

    for pattern in patterns:
        match = re.search(pattern, prompt, flags=re.IGNORECASE)
        if match:
            return _percent_to_fraction(_to_float(match.group(1)))

    raise ValueError("Could not extract impurity limit percentage.")


def plan_blend_optimization_problem(prompt: str, trace_dir: Path | None = None) -> dict:
    product_mass_kg = extract_product_mass_kg(prompt)
    sources = extract_sources(prompt)
    impurity_limit_fraction = extract_impurity_limit_fraction(prompt)

    spec = {
        "problem_type": "blend_cost_optimization",
        "mode": "minimize_cost",
        "flow_basis": "mass",
        "optimization_solver": "glpk",
        "product_mass_kg": product_mass_kg,
        "source1_name": sources[0]["name"],
        "source1_cost_per_kg": sources[0]["cost_per_kg"],
        "source1_impurity_fraction": sources[0]["impurity_fraction"],
        "source2_name": sources[1]["name"],
        "source2_cost_per_kg": sources[1]["cost_per_kg"],
        "source2_impurity_fraction": sources[1]["impurity_fraction"],
        "impurity_limit_fraction": impurity_limit_fraction,
    }

    if trace_dir is not None:
        trace_dir = Path(trace_dir)

        trace = {
            "planner": "deterministic_blend_optimizer_planner",
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
    prompt = "Optimize a blend of 100 kg product using source A cost 2 $/kg impurity 1% and source B cost 1 $/kg impurity 5%, with final impurity limit 3%. What is the minimum cost blend?"
    print(json.dumps(plan_blend_optimization_problem(prompt), indent=2, sort_keys=True))
