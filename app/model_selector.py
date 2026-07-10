import json
from pathlib import Path

from app.registry import load_problem_registry


CATALOG = [
    {
        "problem_type": "utility_emissions_optimization",
        "planner_name": "utility_optimizer",
        "required_any": [
            ["emissions", "co2"],
            ["cost"],
            ["heat", "utility", "steam", "electric"]
        ],
        "positive_terms": [
            "emissions", "co2", "cost", "heat", "utility", "steam", "electric",
            "cap", "limit", "sweep", "tradeoff", "period", "minimize", "optimize"
        ],
        "negative_terms": []
    },
    {
        "problem_type": "general_blend_cost_optimization",
        "planner_name": "general_blend_optimizer",
        "required_any": [
            ["optimize", "minimize"],
            ["blend", "product"],
            ["source a", "source"],
            ["source c", "sulfur", "ash", "quality"]
        ],
        "positive_terms": [
            "source c", "sulfur", "ash", "quality", "final", "at most",
            "minimum", "max", "availability", "kg", "cost"
        ],
        "negative_terms": ["co2", "emissions", "steam", "electric"]
    },
    {
        "problem_type": "blend_cost_optimization",
        "planner_name": "blend_optimizer",
        "required_any": [
            ["optimize", "minimize"],
            ["blend"],
            ["source a"],
            ["source b"],
            ["impurity"]
        ],
        "positive_terms": ["cost", "impurity", "limit", "minimum cost", "product"],
        "negative_terms": ["source c", "sulfur", "ash", "co2", "emissions"]
    },
    {
        "problem_type": "adiabatic_mixer",
        "planner_name": "mixer",
        "required_any": [
            ["mix", "blend"],
            ["water", "stream"],
            ["outlet temperature", "temperature"]
        ],
        "positive_terms": ["kg/s", "kg/hr", "outlet", "adiabatic", "water"],
        "negative_terms": ["cost", "optimize", "minimize", "source a", "source b", "emissions", "co2"]
    },
    {
        "problem_type": "heater_energy_balance",
        "planner_name": "base_energy_balance",
        "required_any": [
            ["heat", "cool", "receives", "removed"],
            ["water", "stream"],
            ["temperature", "outlet", "heat duty", "mass flow", "from"]
        ],
        "positive_terms": ["k", "c", "kw", "kj", "cp", "kg/s", "kg/hr", "heat duty"],
        "negative_terms": ["cost", "optimize", "minimize", "blend", "source", "emissions", "co2", "mix"]
    },
    {
        "problem_type": "stream_splitter",
        "planner_name": "splitter",
        "required_any": [
            ["split", "splitter"],
            ["flow", "stream"],
            ["fraction", "ratio", "outlet"]
        ],
        "positive_terms": ["inlet", "outlet", "mass flow", "kg/s"],
        "negative_terms": ["cost", "optimize", "emissions", "co2"]
    },
    {
        "problem_type": "splitter",
        "planner_name": "splitter",
        "required_any": [
            ["split", "splitter"],
            ["flow", "stream"],
            ["fraction", "ratio", "outlet"]
        ],
        "positive_terms": ["inlet", "outlet", "mass flow", "kg/s"],
        "negative_terms": ["cost", "optimize", "emissions", "co2"]
    }
]


def _matches_any(prompt_lower: str, terms: list[str]) -> bool:
    return any(term in prompt_lower for term in terms)


def _score_catalog_entry(prompt_lower: str, entry: dict) -> tuple[float, list[str]]:
    reasons = []
    score = 0.0

    for group in entry["required_any"]:
        if _matches_any(prompt_lower, group):
            score += 3.0
            reasons.append("matched required group " + str(group))
        else:
            return -100.0, ["missing required group " + str(group)]

    for term in entry.get("positive_terms", []):
        if term in prompt_lower:
            score += 1.0
            reasons.append("matched positive term " + term)

    for term in entry.get("negative_terms", []):
        if term in prompt_lower:
            score -= 2.0
            reasons.append("matched negative term " + term)

    return score, reasons


def select_model_for_prompt(prompt: str, min_score: float = 9.0) -> dict:
    registry = load_problem_registry()
    supported_problem_types = registry["problem_types"]
    prompt_lower = prompt.lower()

    candidates = []

    for entry in CATALOG:
        problem_type = entry["problem_type"]

        if problem_type not in supported_problem_types:
            continue

        score, reasons = _score_catalog_entry(prompt_lower, entry)

        candidates.append(
            {
                "problem_type": problem_type,
                "planner_name": entry["planner_name"],
                "score": score,
                "supported_modes": supported_problem_types[problem_type].get("supported_modes", []),
                "scaffold": supported_problem_types[problem_type].get("scaffold"),
                "reasons": reasons
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)

    selected = candidates[0] if candidates and candidates[0]["score"] >= min_score else None

    return {
        "selector": "registry_keyword_model_selector",
        "prompt": prompt,
        "min_score": min_score,
        "selected_problem_type": selected["problem_type"] if selected else None,
        "selected_planner_name": selected["planner_name"] if selected else None,
        "selected_score": selected["score"] if selected else None,
        "candidates": candidates
    }


def write_model_selection_trace(prompt: str, trace_dir: Path) -> dict:
    trace_dir = Path(trace_dir)
    selection = select_model_for_prompt(prompt)
    (trace_dir / "model_selection_trace.json").write_text(
        json.dumps(selection, indent=2, sort_keys=True),
        encoding="utf-8"
    )
    return selection
