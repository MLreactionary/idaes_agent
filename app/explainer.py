import json
import re
from pathlib import Path

from app.llm_client import call_llm_text, get_llm_metadata


class ExplainerError(Exception):
    pass


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise ExplainerError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def clean_explanation_text(text: str) -> str:
    """
    Deterministically clean LLM explanation text.

    The LLM explanation is allowed to explain only.
    This cleaner removes formatting artifacts and meta-commentary.
    """
    cleaned = text.strip()

    # Remove markdown code fences.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:markdown)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    # If the model adds a second meta paragraph, remove common forms.
    meta_markers = [
        "\n\nThis explanation",
        "\n\nThe explanation",
        "\n\nThis response",
        "\n\nThis summary"
    ]

    for marker in meta_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker)[0].strip()

    return cleaned


def build_explanation_prompt(
    original_prompt: str,
    spec: dict,
    result: dict,
    verification: dict
) -> tuple[str, str]:
    system_prompt = """
You are an engineering explanation component for a controlled process-modeling agent.

Your job:
Explain the verified result in simple engineering language.

Strict rules:
- Do not change any numerical result.
- Do not invent additional calculations.
- Do not claim this is a full IDAES thermodynamic simulation.
- Do not claim general chemical engineering capability.
- Use only the provided prompt, structured spec, parsed result, and verification summary.
- Mention important assumptions/defaults.
- Mention that this MVP uses a sensible-heat model.
- Keep the explanation short and clear.
- Do not wrap the answer in a code block.
- Do not write meta-commentary about your explanation.
- Output only the explanation paragraph.
""".strip()

    user_prompt = f"""
Original prompt:
{original_prompt}

Structured spec:
{json.dumps(spec, indent=2, sort_keys=True)}

Parsed result:
{json.dumps(result, indent=2, sort_keys=True)}

Verification summary:
{json.dumps({
    "verified": verification.get("verified"),
    "num_checks": verification.get("num_checks"),
    "num_failures": verification.get("num_failures"),
    "failures": verification.get("failures", [])
}, indent=2, sort_keys=True)}

Write one short engineering explanation paragraph.
""".strip()

    return system_prompt, user_prompt


def generate_engineering_explanation(
    run_dir: Path,
    original_prompt: str
) -> Path:
    run_dir = Path(run_dir)

    spec = _load_json(run_dir / "structured_spec.json")
    result = _load_json(run_dir / "parsed_result.json")
    verification = _load_json(run_dir / "verification.json")

    if verification.get("verified") is not True:
        raise ExplainerError(
            "Refusing to generate final engineering explanation because the run is not verified."
        )

    system_prompt, user_prompt = build_explanation_prompt(
        original_prompt=original_prompt,
        spec=spec,
        result=result,
        verification=verification
    )

    raw_response = call_llm_text(
        system_prompt=system_prompt,
        user_prompt=user_prompt
    )

    cleaned_response = clean_explanation_text(raw_response)

    metadata = get_llm_metadata()

    explanation_path = run_dir / "llm_engineering_explanation.md"
    raw_response_path = run_dir / "llm_explanation_raw_response.txt"
    prompt_path = run_dir / "llm_explanation_prompt.txt"
    trace_path = run_dir / "llm_explanation_trace.json"

    explanation_path.write_text(cleaned_response + "\n", encoding="utf-8")
    raw_response_path.write_text(raw_response, encoding="utf-8")
    prompt_path.write_text(
        "=== SYSTEM PROMPT ===\n"
        + system_prompt
        + "\n\n=== USER PROMPT ===\n"
        + user_prompt,
        encoding="utf-8"
    )

    trace = {
        "llm": metadata,
        "explanation_path": str(explanation_path),
        "raw_response_path": str(raw_response_path),
        "prompt_path": str(prompt_path),
        "cleaned": cleaned_response != raw_response.strip(),
        "source_files": {
            "structured_spec": str(run_dir / "structured_spec.json"),
            "parsed_result": str(run_dir / "parsed_result.json"),
            "verification": str(run_dir / "verification.json")
        }
    }

    trace_path.write_text(
        json.dumps(trace, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    return explanation_path


if __name__ == "__main__":
    raise SystemExit(
        "Use this through scripts/run_problem.py with --explain."
    )
