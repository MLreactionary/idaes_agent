
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app import llm_client
from app.domain_retriever import build_domain_context


class CodeGenerationError(RuntimeError):
    pass


SYSTEM_PROMPT = "\n".join(
    [
        "You are a scaffold-guided Pyomo code generator for process optimization problems.",
        "Generate a complete executable Python script.",
        "Output only Python code.",
        "Do not output markdown.",
        "Do not explain the code.",
        "The script must build and solve the optimization model directly using Pyomo.",
        "The script must be self contained except for pyomo and standard library imports.",
        "Do not import app.general_blend_domain_solver.",
        "Do not call solve_general_blend_spec.",
        "The script must print RESULT_JSON_START before the result JSON.",
        "The script must print RESULT_JSON_END after the result JSON.",
    ]
)


def extract_python_code(text: str) -> str:
    cleaned = text.strip()

    fence_match = re.search(
        r"```(?:python)?\s*(.*?)```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if fence_match:
        cleaned = fence_match.group(1).strip()

    starts = [
        index
        for index in [
            cleaned.find("from __future__"),
            cleaned.find("import "),
        ]
        if index >= 0
    ]

    if starts:
        cleaned = cleaned[min(starts):].strip()

    return cleaned


def validate_generated_model_code(code: str) -> list[str]:
    errors = []

    required_snippets = [
        "RESULT_JSON_START",
        "RESULT_JSON_END",
        "ConcreteModel",
        "SolverFactory",
        "Objective",
        "Constraint",
    ]

    for snippet in required_snippets:
        if snippet not in code:
            errors.append("Generated code is missing required snippet: " + snippet)

    if "json.dumps" not in code and "json.dump" not in code:
        errors.append("Generated code must serialize the result with json.dumps or json.dump")

    try:
        compile(code, "generated_model.py", "exec")
    except SyntaxError as exc:
        errors.append(f"Generated code has Python syntax error: {exc}")

    required_modeling_snippets = [
        "model.mass_kg",
        "pyo.Var(model.SOURCES",
    ]

    for snippet in required_modeling_snippets:
        if snippet not in code:
            errors.append("Generated code must use indexed source variable pattern: " + snippet)

    forbidden_snippets = [
        "solve_general_blend_spec",
        "app.general_blend_domain_solver",
        "model.__dict__",
        "setattr(model, f\"mass_kg_",
        "getattr(model, f\"mass_kg_",
        "model.total_cost()",
        "source[\"cost_per_kg\"]",
        "source[\"qualities\"]",
    ]

    for snippet in forbidden_snippets:
        if snippet in code:
            errors.append("Generated code uses forbidden pattern: " + snippet + ". Use source_lookup[source_name] instead.")

    return errors


def build_user_prompt(prompt: str, spec: dict[str, Any], solver_name: str, top_k: int) -> str:
    spec_json = json.dumps(spec, indent=2, sort_keys=True)

    return "\n".join(
        [
            "Generate one executable Python script for this linear blend optimization problem.",
            "Output only Python code. No markdown. No explanation.",
            "",
            "Original user prompt:",
            prompt,
            "",
            "Structured spec:",
            spec_json,
            "",
            "Solver name:",
            solver_name,
            "",
            "Required Pyomo scaffold:",
            "1. import json",
            "2. import pyomo.environ as pyo",
            "3. define SPEC exactly from the structured spec",
            "4. define SOLVER_NAME exactly from the solver name",
            "5. create source_lookup = {source[\"name\"]: source for source in SPEC[\"sources\"]}",
            "6. create model = pyo.ConcreteModel()",
            "7. create model.SOURCES from source names",
            "7a. create exactly one indexed decision variable: model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds)",
            "7a. create exactly one indexed decision variable: model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds)",
            "8. create nonnegative mass_kg variables with source min/max bounds when present",
            "9. objective minimizes sum(source_lookup[source_name][\"cost_per_kg\"] * model.mass_kg[source_name])",
            "9a. Use source_lookup[source_name][\"cost_per_kg\"] in the objective.",
            "9b. Use source_lookup[source_name][\"qualities\"][quality_name] in quality constraints.",
            "9c. Never use source[\"cost_per_kg\"] or source[\"qualities\"] inside model expressions.",
            "10. mass balance equals product_mass_kg",
            "11. quality lower constraints use sum(q_i * mass_i) >= lower_bound * product_mass_kg",
            "12. quality upper constraints use sum(q_i * mass_i) <= upper_bound * product_mass_kg",
            "13. for scalar constraints inside loops, use pyo.Constraint(expr=expression), not rule functions with default arguments",
            "14. solve with pyo.SolverFactory(SOLVER_NAME)",
            "15. build a Python dict named result",
            "16. quality_results must be weighted-average qualities",
            "17. include source_results, total_cost, total_blended_mass_kg, mass_balance_residual_kg, solver_status, termination_condition",
            "17a. Convert solver status and termination condition to strings before JSON serialization.",
            "18. do not import app.general_blend_domain_solver",
            "19. never use model.sources.index or model.SOURCES.index",
            "20. final three lines must be exactly:",
            "print(\"RESULT_JSON_START\")",
            "print(json.dumps(result, indent=2, sort_keys=True))",
            "print(\"RESULT_JSON_END\")",
        ]
    )



def repair_generated_model_code(
    prompt: str,
    spec: dict[str, Any],
    solver_name: str,
    broken_code: str,
    validation_errors: list[str],
    top_k: int,
) -> str:
    spec_json = json.dumps(spec, indent=2, sort_keys=True)
    broken_excerpt = broken_code[:2500]

    repair_prompt = "\n".join(
        [
            "Rewrite the failed generated Pyomo script.",
            "Output only executable Python code. No markdown. No explanation.",
            "",
            "Structured spec:",
            spec_json,
            "",
            "Solver name:",
            solver_name,
            "",
            "Validation errors:",
            json.dumps(validation_errors, indent=2),
            "",
            "Broken code excerpt:",
            broken_excerpt,
            "",
            "Required implementation:",
            "1. import json",
            "2. import pyomo.environ as pyo",
            "3. define SPEC from the structured spec",
            "4. define SOLVER_NAME from the solver name",
            "5. create source_lookup = {source[\"name\"]: source for source in SPEC[\"sources\"]}",
            "6. build pyo.ConcreteModel() directly",
            "7. create exactly one indexed decision variable: model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds)",
            "8. minimize sum(cost_per_kg * mass_kg)",
            "9. enforce total mass equals product_mass_kg",
            "10. enforce quality_lower_bounds using weighted sums >= bound * product_mass_kg",
            "11. enforce quality_upper_bounds using weighted sums <= bound * product_mass_kg",
            "12. solve with pyo.SolverFactory(SOLVER_NAME)",
            "13. build a Python dict named result",
            "14. quality_results must be weighted average quality, not total mass of quality",
            "15. never use model.sources.index or model.SOURCES.index",
            "16. never print JSON manually field by field",
            "17. final three lines must be exactly:",
            "print(\"RESULT_JSON_START\")",
            "print(json.dumps(result, indent=2, sort_keys=True))",
            "print(\"RESULT_JSON_END\")",
        ]
    )

    raw_response = llm_client.call_llm_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=repair_prompt,
    )

    return extract_python_code(raw_response)



def write_codegen_trace(trace_dir: Path, payload: dict[str, Any]) -> None:
    trace_dir.mkdir(parents=True, exist_ok=True)
    (trace_dir / "codegen_trace.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def repair_generated_model_code_after_runtime(
    prompt: str,
    spec: dict[str, Any],
    solver_name: str,
    broken_code: str,
    raw_output: str,
    top_k: int = 5,
) -> str:
    spec_json = json.dumps(spec, indent=2, sort_keys=True)

    runtime_prompt = "\n".join(
        [
            "The generated Pyomo script passed static validation but failed at runtime.",
            "Repair the entire script.",
            "Output only executable Python code. No markdown. No explanation.",
            "",
            "Structured spec:",
            spec_json,
            "",
            "Solver name:",
            solver_name,
            "",
            "Runtime traceback/output:",
            raw_output[-3000:],
            "",
            "Broken generated code:",
            broken_code[:5000],
            "",
            "Important Pyomo rules:",
            "1. For scalar constraints created inside loops, prefer pyo.Constraint(expr=expression).",
            "2. Do not define loop constraints as def rule(model, q=quality), because Pyomo may pass None as an index.",
            "3. Use source_lookup dictionaries for costs and qualities.",
            "3d. In objective use source_lookup[source_name][\"cost_per_kg\"].",
            "3e. In quality constraints use source_lookup[source_name][\"qualities\"][quality_name].",
            "3f. Never use source[\"cost_per_kg\"] or source[\"qualities\"] in expressions.",
            "3b. Use model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds).",
            "3c. Never use setattr/getattr/model.__dict__ to create source variables.",
            "3a. Use exactly one indexed variable model.mass_kg[source_name]. Do not create dynamic scalar variables with setattr/getattr.",
            "3a. Use exactly one indexed variable model.mass_kg[source_name]. Do not create dynamic scalar variables with setattr/getattr.",
            "4. Never use model.sources.index or model.SOURCES.index.",
            "5. quality_results must be weighted-average quality, not total quality mass.",
            "6. Build a dict named result.",
            "7. Do not manually print JSON field by field.",
            "8. Final three lines must be exactly:",
            "print(\"RESULT_JSON_START\")",
            "print(json.dumps(result, indent=2, sort_keys=True))",
            "print(\"RESULT_JSON_END\")",
        ]
    )

    raw_response = llm_client.call_llm_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=runtime_prompt,
    )

    repaired_code = extract_python_code(raw_response)
    validation_errors = validate_generated_model_code(repaired_code)

    if validation_errors:
        raise CodeGenerationError("Runtime repair failed validation: " + "; ".join(validation_errors))

    return repaired_code



def generate_scaffold_guided_model_code(
    prompt: str,
    spec: dict[str, Any],
    solver_name: str = "glpk",
    trace_dir: str | Path | None = None,
    top_k: int = 5,
) -> str:
    user_prompt = build_user_prompt(
        prompt=prompt,
        spec=spec,
        solver_name=solver_name,
        top_k=top_k,
    )

    raw_response = llm_client.call_llm_text(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    code = extract_python_code(raw_response)
    validation_errors = validate_generated_model_code(code)

    repair_code = None
    repair_validation_errors = []

    if validation_errors:
        repair_code = repair_generated_model_code(
            prompt=prompt,
            spec=spec,
            solver_name=solver_name,
            broken_code=code,
            validation_errors=validation_errors,
            top_k=top_k,
        )
        repair_validation_errors = validate_generated_model_code(repair_code)

        if not repair_validation_errors:
            code = repair_code
            validation_errors = []

    trace_payload = {
        "system_prompt": SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "raw_response": raw_response,
        "generated_code": code,
        "initial_validation_errors": validation_errors,
        "repair_code": repair_code,
        "repair_validation_errors": repair_validation_errors,
    }

    if trace_dir is not None:
        write_codegen_trace(Path(trace_dir), trace_payload)

    if validation_errors:
        raise CodeGenerationError("; ".join(validation_errors))

    return code
