import json
import re
from pathlib import Path


def is_general_blend_optimization_prompt(prompt: str) -> bool:
    prompt_lower = prompt.lower()

    return (
        ("optimize" in prompt_lower or "minimize" in prompt_lower or "minimum cost" in prompt_lower)
        and ("blend" in prompt_lower or "source" in prompt_lower)
        and ("cost" in prompt_lower)
        and (
            "source c" in prompt_lower
            or "sulfur" in prompt_lower
            or "ash" in prompt_lower
            or "moisture" in prompt_lower
            or "quality" in prompt_lower
        )
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


def _extract_quality_pairs(text: str) -> dict:
    pairs = {}

    for name, value in re.findall(
        r"\b([A-Za-z][A-Za-z0-9_]*)\s+([-+]?\d+(?:\.\d+)?)\s*%",
        text,
        flags=re.IGNORECASE
    ):
        key = name.lower()

        if key in {"cost", "source", "final", "limit"}:
            continue

        pairs[key] = _percent_to_fraction(_to_float(value))

    return pairs


def extract_sources(prompt: str) -> list[dict]:
    pattern = re.compile(
        r"source\s+([A-Za-z0-9_]+)"
        r"\s+cost\s+([-+]?\d+(?:,\d{3})*(?:\.\d+)?)"
        r"\s*(?:\$|usd)?\s*/\s*kg"
        r"\s+(.*?)(?=(?:,\s*)?(?:and\s+)?source\s+[A-Za-z0-9_]+\s+cost|\.|final\s+|with\s+final\s+|$)",
        flags=re.IGNORECASE | re.DOTALL
    )

    sources = []

    for match in pattern.finditer(prompt):
        name = match.group(1)
        cost = _to_float(match.group(2))
        quality_text = match.group(3)
        qualities = _extract_quality_pairs(quality_text)

        if not qualities:
            raise ValueError(f"Could not extract quality percentages for source {name}.")

        sources.append(
            {
                "name": name,
                "cost_per_kg": cost,
                "qualities": qualities
            }
        )

    if len(sources) < 2:
        raise ValueError(f"Expected at least two sources, found {len(sources)}.")

    return sources


def extract_quality_limits(prompt: str) -> dict:
    limits = {}

    patterns = [
        r"\b([A-Za-z][A-Za-z0-9_]*)\s+must\s+be\s+(?:at\s+most|below|under|<=|less\s+than)\s+([-+]?\d+(?:\.\d+)?)\s*%",
        r"\b([A-Za-z][A-Za-z0-9_]*)\s+(?:limit|maximum|max)\s+([-+]?\d+(?:\.\d+)?)\s*%",
    ]

    for pattern in patterns:
        for name, value in re.findall(pattern, prompt, flags=re.IGNORECASE):
            key = name.lower()

            if key in {"final", "source", "cost"}:
                continue

            limits[key] = _percent_to_fraction(_to_float(value))

    if not limits:
        raise ValueError("Could not extract quality limits.")

    return limits


def validate_sources_against_limits(sources: list[dict], quality_limits: dict):
    required_qualities = set(quality_limits)

    for source in sources:
        source_qualities = set(source["qualities"])
        missing = sorted(required_qualities - source_qualities)

        if missing:
            raise ValueError(
                f"Source {source['name']} is missing qualities required by limits: {missing}"
            )


def plan_general_blend_optimization_problem(prompt: str, trace_dir: Path | None = None) -> dict:
    product_mass_kg = extract_product_mass_kg(prompt)
    sources = extract_sources(prompt)
    quality_limits = extract_quality_limits(prompt)

    validate_sources_against_limits(sources, quality_limits)

    spec = {
        "problem_type": "general_blend_cost_optimization",
        "mode": "minimize_cost",
        "flow_basis": "mass",
        "optimization_solver": "glpk",
        "product_mass_kg": product_mass_kg,
        "sources": sources,
        "quality_limits": quality_limits
    }

    if trace_dir is not None:
        trace_dir = Path(trace_dir)

        trace = {
            "planner": "deterministic_general_blend_optimizer_planner",
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
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, "
        "source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. "
        "Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost."
    )
    print(json.dumps(plan_general_blend_optimization_problem(prompt), indent=2, sort_keys=True))
