
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from app import llm_client
from app.domain_retriever import build_domain_context, retrieve_domain_chunks


class SpecExtractionError(RuntimeError):
    pass


def extract_first_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()

    # Some LLM/test outputs contain literal escaped newlines and quotes.
    # Convert those into normal JSON text before scanning.
    if "\\n" in cleaned or "\\\"" in cleaned:
        cleaned = cleaned.replace("\\n", "\n").replace("\\\"", "\"")

    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned.strip(), flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned.strip()).strip()

    start = cleaned.find("{")

    if start < 0:
        raise SpecExtractionError("LLM response did not contain a JSON object.")

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(cleaned)):
        char = cleaned[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "\"":
                in_string = False
            continue

        if char == "\"":
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start:index + 1]
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError as exc:
                    raise SpecExtractionError(f"Could not parse JSON object: {exc}") from exc

                if not isinstance(parsed, dict):
                    raise SpecExtractionError("Extracted JSON is not an object.")

                return parsed

    raise SpecExtractionError("Could not find a complete JSON object in LLM response.")


def normalize_key(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip().lower()).strip("_")


def normalize_number(value: Any) -> float:
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("$", "").replace("%", "").strip()
        return float(cleaned)

    return float(value)


def normalize_fraction(value: Any) -> float:
    number = normalize_number(value)

    if number > 1.0 and number <= 100.0:
        return number / 100.0

    return number


def normalize_general_blend_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(spec)

    normalized["problem_type"] = "general_blend_cost_optimization"
    normalized.setdefault("objective", "minimize_cost")

    if "product_mass_kg" in normalized:
        normalized["product_mass_kg"] = normalize_number(normalized["product_mass_kg"])

    sources = []

    for source in normalized.get("sources", []):
        source_out = dict(source)
        source_out["name"] = normalize_key(source_out.get("name", "source"))

        if "cost_per_kg" in source_out:
            source_out["cost_per_kg"] = normalize_number(source_out["cost_per_kg"])

        if "max_available_kg" in source_out and source_out["max_available_kg"] is not None:
            source_out["max_available_kg"] = normalize_number(source_out["max_available_kg"])

        if "min_required_kg" in source_out and source_out["min_required_kg"] is not None:
            source_out["min_required_kg"] = normalize_number(source_out["min_required_kg"])

        qualities = {}

        for quality_name, quality_value in source_out.get("qualities", {}).items():
            qualities[normalize_key(quality_name)] = normalize_fraction(quality_value)

        source_out["qualities"] = qualities
        sources.append(source_out)

    normalized["sources"] = sources

    for field in ["quality_lower_bounds", "quality_upper_bounds", "quality_targets"]:
        if field in normalized and normalized[field] is not None:
            normalized[field] = {
                normalize_key(name): normalize_fraction(value)
                for name, value in normalized[field].items()
            }

    return normalized


def validate_general_blend_spec(spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if spec.get("problem_type") != "general_blend_cost_optimization":
        errors.append("problem_type must be general_blend_cost_optimization.")

    if spec.get("objective") not in {"minimize_cost", "minimize_total_cost"}:
        errors.append("objective must be minimize_cost.")

    product_mass = spec.get("product_mass_kg")

    if product_mass is None:
        errors.append("product_mass_kg is required.")
    else:
        try:
            if float(product_mass) <= 0:
                errors.append("product_mass_kg must be positive.")
        except Exception:
            errors.append("product_mass_kg must be numeric.")

    sources = spec.get("sources")

    if not isinstance(sources, list) or len(sources) < 2:
        errors.append("sources must contain at least two source objects.")
    else:
        quality_names: set[str] = set()

        for index, source in enumerate(sources):
            prefix = f"sources[{index}]"

            if not source.get("name"):
                errors.append(f"{prefix}.name is required.")

            if "cost_per_kg" not in source:
                errors.append(f"{prefix}.cost_per_kg is required.")

            qualities = source.get("qualities")

            if not isinstance(qualities, dict) or not qualities:
                errors.append(f"{prefix}.qualities must be a nonempty object.")
            else:
                quality_names.update(qualities.keys())

        lower_bounds = spec.get("quality_lower_bounds", {}) or {}
        upper_bounds = spec.get("quality_upper_bounds", {}) or {}

        if not lower_bounds and not upper_bounds:
            errors.append("At least one quality lower or upper bound is required.")

        for quality_name in list(lower_bounds.keys()) + list(upper_bounds.keys()):
            if quality_name not in quality_names:
                errors.append(
                    f"Quality bound {quality_name} is not present in source qualities."
                )

    return errors


def build_extraction_system_prompt() -> str:
    return """You are a process systems optimization spec extractor.

Your task is to convert a natural language blending or formulation optimization problem into one strict JSON object.

Do not solve the optimization problem.
Do not explain.
Do not include markdown.
Return only JSON.

Use this normalized schema:
{
  "problem_type": "general_blend_cost_optimization",
  "product_mass_kg": number,
  "objective": "minimize_cost",
  "sources": [
    {
      "name": string,
      "cost_per_kg": number,
      "qualities": {
        "quality_name": number
      },
      "min_required_kg": optional number,
      "max_available_kg": optional number
    }
  ],
  "quality_lower_bounds": optional object,
  "quality_upper_bounds": optional object,
  "notes": optional array of strings
}

Important rules:
- Convert percentages to fractions.
- 9 percent becomes 0.09.
- at least means quality_lower_bounds.
- minimum means quality_lower_bounds unless it describes source usage.
- at most means quality_upper_bounds.
- maximum means quality_upper_bounds unless it describes source availability.
- Keep arbitrary quality names such as protein, fiber, sulfur, ash, iron, grade, purity, octane.
- Use kg as the normalized product mass unit if the prompt gives kg.
- If a source has an availability limit, use max_available_kg.
- If a source must be used at least a certain amount, use min_required_kg.
"""


def build_extraction_user_prompt(prompt: str, domain_context: str) -> str:
    return f"""User prompt:
{prompt}

Retrieved domain context:
{domain_context}

Return the normalized JSON spec only.
"""


def build_repair_prompt(
    prompt: str,
    domain_context: str,
    invalid_spec: dict[str, Any],
    errors: list[str],
) -> str:
    return f"""The previous JSON spec was invalid.

Original user prompt:
{prompt}

Retrieved domain context:
{domain_context}

Invalid JSON spec:
{json.dumps(invalid_spec, indent=2, sort_keys=True)}

Validation errors:
{json.dumps(errors, indent=2)}

Return a corrected normalized JSON spec only.
"""


def extract_general_blend_spec(
    prompt: str,
    trace_dir: Path | None = None,
    top_k: int = 5,
    repair_attempts: int = 1,
) -> dict[str, Any]:
    chunks = retrieve_domain_chunks(prompt=prompt, domain="general_blend", top_k=top_k)
    domain_context = build_domain_context(prompt=prompt, domain="general_blend", top_k=top_k)

    system_prompt = build_extraction_system_prompt()
    user_prompt = build_extraction_user_prompt(prompt, domain_context)

    raw_response = llm_client.call_llm_text(system_prompt, user_prompt)
    parsed = extract_first_json_object(raw_response)
    spec = normalize_general_blend_spec(parsed)
    errors = validate_general_blend_spec(spec)

    repair_raw_response = None

    if errors and repair_attempts > 0:
        repair_prompt = build_repair_prompt(
            prompt=prompt,
            domain_context=domain_context,
            invalid_spec=spec,
            errors=errors,
        )

        repair_raw_response = llm_client.call_llm_text(system_prompt, repair_prompt)
        repaired = extract_first_json_object(repair_raw_response)
        spec = normalize_general_blend_spec(repaired)
        errors = validate_general_blend_spec(spec)

    trace = {
        "prompt": prompt,
        "domain": "general_blend",
        "retrieved_chunks": [
            {
                "title": chunk.title,
                "path": chunk.path,
                "score": chunk.score,
            }
            for chunk in chunks
        ],
        "raw_response": raw_response,
        "repair_raw_response": repair_raw_response,
        "spec": spec,
        "validation_errors": errors,
        "valid": not errors,
    }

    if trace_dir is not None:
        trace_dir.mkdir(parents=True, exist_ok=True)
        (trace_dir / "llm_spec_extraction_trace.json").write_text(
            json.dumps(trace, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if errors:
        raise SpecExtractionError("Invalid extracted spec: " + "; ".join(errors))

    return spec


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt")
    parser.add_argument("--trace-dir", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--repair-attempts", type=int, default=1)

    args = parser.parse_args()

    trace_dir = Path(args.trace_dir) if args.trace_dir else None

    spec = extract_general_blend_spec(
        prompt=args.prompt,
        trace_dir=trace_dir,
        top_k=args.top_k,
        repair_attempts=args.repair_attempts,
    )

    print(json.dumps(spec, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
