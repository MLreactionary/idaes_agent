import json
from pathlib import Path

from app.registry import validate_spec, get_problem_type


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CodegenError(Exception):
    pass


def render_model_code(spec: dict) -> str:
    """
    Render generated_model.py from a validated structured spec.

    For now this is deterministic template rendering.
    Later, the LLM will edit only controlled regions inside the scaffold.
    """
    validated_spec = validate_spec(spec)

    problem_config = get_problem_type(validated_spec["problem_type"])
    scaffold_rel_path = problem_config["scaffold"]
    scaffold_path = PROJECT_ROOT / scaffold_rel_path

    if not scaffold_path.exists():
        raise CodegenError(f"Scaffold not found: {scaffold_path}")

    template = scaffold_path.read_text(encoding="utf-8")

    spec_json = json.dumps(validated_spec, indent=2, sort_keys=True)

    if "{{SPEC_JSON}}" not in template:
        raise CodegenError("Scaffold is missing required placeholder: {{SPEC_JSON}}")

    rendered = template.replace("{{SPEC_JSON}}", spec_json)

    return rendered


def write_generated_model(spec: dict, run_dir: Path) -> Path:
    """
    Validate spec, render scaffold, and write generated_model.py.
    """
    run_dir.mkdir(parents=True, exist_ok=True)

    validated_spec = validate_spec(spec)

    spec_path = run_dir / "structured_spec.json"
    model_path = run_dir / "generated_model.py"

    spec_path.write_text(
        json.dumps(validated_spec, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    rendered_code = render_model_code(validated_spec)
    model_path.write_text(rendered_code, encoding="utf-8")

    return model_path


if __name__ == "__main__":
    demo_spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0
    }

    output_dir = PROJECT_ROOT / "outputs" / "runs" / "codegen_test"
    model_path = write_generated_model(demo_spec, output_dir)

    print(f"Wrote generated model: {model_path}")
