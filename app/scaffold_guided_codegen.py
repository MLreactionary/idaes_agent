
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app import llm_client
from app.domain_retriever import build_domain_context


class CodeGenerationError(RuntimeError):
    pass



GOLDEN_SCAFFOLD_PATH = (
    Path(__file__).resolve().parents[1]
    / "knowledge"
    / "domains"
    / "general_blend"
    / "scaffolds"
    / "golden_pyomo_model.py"
)


def load_golden_blend_scaffold() -> str:
    return GOLDEN_SCAFFOLD_PATH.read_text(encoding="utf-8")


SYSTEM_PROMPT = "\n".join(
    [
        "You are a formulation-plan-guided Pyomo code generator for linear blending optimization.",
        "Generate a complete executable Python script.",
        "Output only Python code.",
        "Do not output markdown.",
        "Do not explain the code.",
        "You are given a validated structured spec, a formulation plan, a required result JSON contract, and a golden Pyomo scaffold.",
        "Use the structured spec as the single source of truth.",
        "Use the formulation plan to choose the modeling pattern.",
        "Use the golden scaffold as the coding pattern.",
        "Do not reinterpret the original natural-language prompt.",
        "Do not change units, bounds, source names, quality names, or objective.",
        "Do not solve the optimization manually.",
        "Do not invent a new Pyomo variable structure.",
        "Write minimal Pyomo code with no unnecessary helper logic.",
        "For single-product linear blends, use exactly one indexed variable model.mass_kg[source_name].",
        "Use model.SOURCES and source_lookup[source_name].",
        "Use source_bounds for min_required_kg and max_available_kg.",
        "Build weighted-average quality constraints from quality_lower_bounds and quality_upper_bounds.",
        "The script must build and solve the optimization model directly using Pyomo.",
        "The script must be self contained except for pyomo and standard library imports.",
        "Do not import app.general_blend_domain_solver.",
        "Do not call solve_general_blend_spec.",
        "The script must print RESULT_JSON_START before the result JSON.",
        "The script must print RESULT_JSON_END after the result JSON.",
        "If the solver termination is not optimal, print solver_status and termination_condition without reading variable values.",
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

    if ("max_available_kg" in code or "min_required_kg" in code) and "bounds=source_bounds" not in code:
        errors.append("Generated code must use model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds) when source bounds exist.")

    if "bounds=source_bounds" in code and "def source_bounds" not in code:
        errors.append("Generated code must define source_bounds as a function: def source_bounds(m, source_name), not as a dictionary.")

    if "model.SOURCES" in code and "model.SOURCES = pyo.Set" not in code:
        errors.append("Generated code must define model.SOURCES = pyo.Set(initialize=list(source_lookup.keys())) before using model.SOURCES.")

    forbidden_snippets = [
        "solve_general_blend_spec",
        "app.general_blend_domain_solver",
        "model.__dict__",
        "setattr(model, f\"mass_kg_",
        "getattr(model, f\"mass_kg_",
        "model.total_cost()",
        "source[\"cost_per_kg\"]",
        "source[\"qualities\"]",
        "model.mass_kg.items()",
        "model.mass_kg.values()",
        "sum(model.mass_kg.values())",
        "abs(sum(model.mass_kg.values())",
        "source_bounds = {",
        "(source_name,):",
    ]

    for snippet in forbidden_snippets:
        if snippet in code:
            errors.append("Generated code uses forbidden pattern: " + snippet + ". Use source_lookup[source_name] instead.")

    return errors



def build_linear_blend_formulation_plan(spec: dict[str, Any]) -> dict[str, Any]:
    sources = spec.get("sources", []) or []
    lower_bounds = spec.get("quality_lower_bounds", {}) or {}
    upper_bounds = spec.get("quality_upper_bounds", {}) or {}

    has_upper_bounds = any(
        source.get("max_available_kg") is not None
        for source in sources
    )
    has_lower_bounds = any(
        source.get("min_required_kg") is not None
        for source in sources
    )

    return {
        "problem_family": "linear_blend",
        "formulation_type": "single_product_linear_blend",
        "decision_variable_shape": "x[source]",
        "pyomo_variable_name": "model.mass_kg[source_name]",
        "objective": "minimize_total_cost",
        "objective_expression": "sum(cost_per_kg[source] * x[source] for source in sources)",
        "demand_constraint": "sum(x[source] for source in sources) == product_mass_kg",
        "source_bounds": {
            "has_upper_bounds": has_upper_bounds,
            "has_lower_bounds": has_lower_bounds,
            "implementation": "use bounds=source_bounds on model.mass_kg",
        },
        "quality_constraints": {
            "lower_bounds": sorted(lower_bounds.keys()),
            "upper_bounds": sorted(upper_bounds.keys()),
            "lower_form": "sum(q[source, quality] * x[source]) >= lower_bound[quality] * product_mass_kg",
            "upper_form": "sum(q[source, quality] * x[source]) <= upper_bound[quality] * product_mass_kg",
        },
        "solver_class": "linear_program",
        "recommended_scaffold": "single_product_linear_blend",
        "required_result_contract": [
            "source_results",
            "total_cost",
            "total_blended_mass_kg",
            "mass_balance_residual_kg",
            "quality_results",
            "solver_status",
            "termination_condition",
        ],
    }


def build_user_prompt(prompt: str, spec: dict[str, Any], solver_name: str, top_k: int) -> str:
    spec_json = json.dumps(spec, indent=2, sort_keys=True)
    formulation_plan = build_linear_blend_formulation_plan(spec)
    formulation_plan_json = json.dumps(formulation_plan, indent=2, sort_keys=True)
    golden_scaffold = load_golden_blend_scaffold()

    return "\n".join(
        [
            "Generate one executable Python script for this linear blend optimization problem.",
            "Output only Python code. No markdown. No explanation.",
            "",
            "You are given a validated structured spec and a formulation plan.",
            "The original natural-language prompt is reference only.",
            "Do not reinterpret the original prompt.",
            "Do not change units, bounds, source names, quality names, or objective.",
            "Use the structured spec as the single source of truth.",
            "",
            "Original user prompt for reference only:",
            prompt,
            "",
            "Validated structured spec:",
            spec_json,
            "",
            "Formulation plan:",
            formulation_plan_json,
            "",
            "Required result JSON contract:",
            json.dumps(formulation_plan["required_result_contract"], indent=2),
            "",
            "Golden generic Pyomo scaffold to copy exactly. Copy this structure. Replace only SPEC and SOLVER_NAME. Do not invent a new Pyomo variable structure.",
            "```python",
            load_golden_blend_scaffold(),
            "```",
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
            "7b. Never create one variable per source.",
            "7c. Never use model.__dict__ for variables or constraints.",
            "7d. Never use setattr or getattr for mass variables.",
            "7e. All source decisions must be accessed as model.mass_kg[source_name].",
            "8d. source_bounds must be a function, not a dictionary.",
            "8e. Correct pattern: def source_bounds(m, source_name): return (0.0, source_lookup[source_name].get(\"max_available_kg\"))",
            "8f. Never write source_bounds = {...}.",
            "8g. Never key bounds by (source_name,).",
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
            "17b. Every numeric value placed in result JSON must be a Python float, not a Pyomo object.",
            "17c. Use float(pyo.value(model.mass_kg[source_name])) for source masses.",
            "17d. Never use model.mass_kg.items() or model.mass_kg.values() when building result JSON.",
            "17e. Never put Pyomo VarData, Objective, Expression, or AbsExpression objects into json.dumps.",
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
            "Golden generic Pyomo scaffold to copy exactly. Copy this structure. Replace only SPEC and SOLVER_NAME. Do not invent a new Pyomo variable structure.",
            "```python",
            load_golden_blend_scaffold(),
            "```",
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
            "Golden generic Pyomo scaffold to copy exactly. Copy this structure. Replace only SPEC and SOLVER_NAME. Do not invent a new Pyomo variable structure.",
            "```python",
            load_golden_blend_scaffold(),
            "```",
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
            "3g. The runtime error may be caused by Pyomo objects not being JSON serializable.",
            "3h. Convert all solution values with float(pyo.value(...)) before json.dumps.",
            "3i. Never use model.mass_kg.items() or model.mass_kg.values() in the result dictionary.",
            "3j. Build source_results by looping over model.SOURCES and reading float(pyo.value(model.mass_kg[source_name])).",
            "3b. Use model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds).",
            "3b1. source_bounds must be a function: def source_bounds(m, source_name): return (lb, ub).",
            "3b2. Never define source_bounds as a dictionary.",
            "3b3. Never key source bounds by (source_name,).",
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
