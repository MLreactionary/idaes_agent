import json
import re
from pathlib import Path

from app.llm_client import call_llm_text, get_llm_metadata
from app.registry import load_problem_registry, validate_spec
from app.spec_reconciler import reconcile_spec_with_prompt


class LLMPlannerError(Exception):
    pass


def extract_json_object(text: str) -> dict:
    """
    Extract a JSON object from LLM output.

    Handles:
    - raw JSON
    - ```json fenced JSON
    - accidental text before/after JSON
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise LLMPlannerError(f"Could not find JSON object in LLM output:\n{text}")

    json_text = text[start:end + 1]

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise LLMPlannerError(f"Invalid JSON from LLM: {exc}\nRaw output:\n{text}") from exc


def build_planner_system_prompt() -> str:
    registry = load_problem_registry()
    supported_problem_types = registry["problem_types"]

    return f"""
You are the planning component of a controlled process-engineering modeling agent.

Your job is to convert a natural-language process modeling prompt into a structured JSON specification.

You do not solve the numerical problem.
You do not verify results.
You do not write code.
You do not invent unsupported process models.

Supported problem registry:
{json.dumps(supported_problem_types, indent=2, sort_keys=True)}

Currently supported scope:
- heater_energy_balance only
- single stream only
- sensible heat balance only
- water-like liquid stream is allowed
- no reaction
- no phase equilibrium
- no flash
- no separator
- no optimization
- no full flowsheet

Supported modes:
1. calculate_heat_duty
   Use this when the prompt gives inlet temperature and outlet temperature and asks for heat duty.

2. calculate_outlet_temperature
   Use this when the prompt gives inlet temperature and heat duty and asks for outlet temperature.

Rules:
- Return JSON only.
- Use problem_type = "heater_energy_balance" for supported heater/cooler prompts.
- Use mode = "calculate_heat_duty" when both inlet and outlet temperatures are given.
- Use mode = "calculate_outlet_temperature" when inlet temperature and heat duty are given.
- Convert Celsius to Kelvin.
- Convert bar to Pa.
- Convert kW to W.
- Convert MW to W.
- Convert kg/s to mass_flow_kg_s.
- If mass flow is missing, omit mass_flow_kg_s and let the backend default apply.
- If material is water, include "material": "water".
- If Cp is not explicitly stated, omit cp_j_kg_k and let the backend default apply.
- If pressure is not stated, omit pressure_pa and let the backend default apply.
- If heat is removed, heat_duty_w must be negative.
- If heat is added/received, heat_duty_w must be positive.
- Do not include comments.
- Do not include markdown.

If the prompt is unsupported, return:
{{
  "unsupported": true,
  "reason": "clear reason here"
}}

Examples:

Prompt:
Heat a water stream from 300 K to 350 K at 1 bar and report heat duty.

Output:
{{
  "problem_type": "heater_energy_balance",
  "mode": "calculate_heat_duty",
  "material": "water",
  "temperature_in_k": 300.0,
  "temperature_out_k": 350.0,
  "pressure_pa": 100000.0
}}

Prompt:
Cool water from 80 C to 30 C at 2 kg/s and report the heat duty.

Output:
{{
  "problem_type": "heater_energy_balance",
  "mode": "calculate_heat_duty",
  "material": "water",
  "mass_flow_kg_s": 2.0,
  "temperature_in_k": 353.15,
  "temperature_out_k": 303.15
}}

Prompt:
Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?

Output:
{{
  "problem_type": "heater_energy_balance",
  "mode": "calculate_outlet_temperature",
  "material": "water",
  "temperature_in_k": 300.0,
  "heat_duty_w": 100000.0
}}

Prompt:
Water enters at 350 K and 50 kW of heat is removed. What is the outlet temperature?

Output:
{{
  "problem_type": "heater_energy_balance",
  "mode": "calculate_outlet_temperature",
  "material": "water",
  "temperature_in_k": 350.0,
  "heat_duty_w": -50000.0
}}
""".strip()


def write_planner_trace(
    trace_dir: Path,
    prompt: str,
    system_prompt: str,
    user_prompt: str,
    raw_output: str,
    extracted_json: dict | None,
    validated_spec: dict | None,
    error: str | None = None
) -> None:
    trace_dir = Path(trace_dir)
    trace_dir.mkdir(parents=True, exist_ok=True)

    metadata = get_llm_metadata()

    (trace_dir / "planner_system_prompt.txt").write_text(system_prompt, encoding="utf-8")
    (trace_dir / "planner_user_prompt.txt").write_text(user_prompt, encoding="utf-8")
    (trace_dir / "planner_raw_response.txt").write_text(raw_output, encoding="utf-8")

    if extracted_json is not None:
        (trace_dir / "planner_extracted.json").write_text(
            json.dumps(extracted_json, indent=2, sort_keys=True),
            encoding="utf-8"
        )

    if validated_spec is not None:
        (trace_dir / "planner_validated_spec.json").write_text(
            json.dumps(validated_spec, indent=2, sort_keys=True),
            encoding="utf-8"
        )

    trace = {
        "prompt": prompt,
        "llm": metadata,
        "raw_response_path": str(trace_dir / "planner_raw_response.txt"),
        "extracted_json_path": str(trace_dir / "planner_extracted.json"),
        "validated_spec_path": str(trace_dir / "planner_validated_spec.json"),
        "error": error
    }

    (trace_dir / "planner_trace.json").write_text(
        json.dumps(trace, indent=2, sort_keys=True),
        encoding="utf-8"
    )


def plan_problem_with_llm(prompt: str, trace_dir: Path | None = None) -> dict:
    system_prompt = build_planner_system_prompt()

    user_prompt = f"""
Natural-language process problem:

{prompt}

Return only the JSON object.
""".strip()

    raw_output = ""
    extracted = None
    validated = None

    try:
        raw_output = call_llm_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt
        )

        extracted = extract_json_object(raw_output)

        if extracted.get("unsupported") is True:
            reason = extracted.get("reason", "Unsupported problem.")

            if trace_dir is not None:
                write_planner_trace(
                    trace_dir=trace_dir,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    raw_output=raw_output,
                    extracted_json=extracted,
                    validated_spec=None,
                    error=reason
                )

            raise LLMPlannerError(reason)

        # Deterministic reconciliation protects against LLM numeric-copying errors.
        reconciled, reconciliation_changes = reconcile_spec_with_prompt(
            extracted,
            prompt
        )

        # Deterministic backend validation.
        validated = validate_spec(reconciled)

        if trace_dir is not None:
            write_planner_trace(
                trace_dir=trace_dir,
                prompt=prompt,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_output=raw_output,
                extracted_json=extracted,
                validated_spec=validated,
                error=None
            )

            (Path(trace_dir) / "planner_reconciliation_changes.json").write_text(
                json.dumps(reconciliation_changes, indent=2, sort_keys=True),
                encoding="utf-8"
            )

            (Path(trace_dir) / "planner_reconciled.json").write_text(
                json.dumps(reconciled, indent=2, sort_keys=True),
                encoding="utf-8"
            )

        return validated

    except Exception as exc:
        if trace_dir is not None and raw_output:
            write_planner_trace(
                trace_dir=trace_dir,
                prompt=prompt,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                raw_output=raw_output,
                extracted_json=extracted,
                validated_spec=validated,
                error=f"{type(exc).__name__}: {exc}"
            )

        raise


if __name__ == "__main__":
    demo_prompt = "I have water at 27 C and I want to heat it to 77 C at 1 bar. What heat duty is needed?"
    spec = plan_problem_with_llm(demo_prompt)
    print(json.dumps(spec, indent=2, sort_keys=True))
