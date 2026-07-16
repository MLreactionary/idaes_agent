
from app import scaffold_guided_codegen as codegen


def test_extract_python_code_from_markdown():
    raw = """```python
import json
import pyomo.environ as pyo
model = pyo.ConcreteModel()
solver = pyo.SolverFactory("glpk")
print("RESULT_JSON_START")
print(json.dumps({"solver_status": "ok"}))
print("RESULT_JSON_END")
```"""

    code = codegen.extract_python_code(raw)

    assert code.startswith("import json")
    assert "RESULT_JSON_START" in code
    assert "RESULT_JSON_END" in code


def test_validate_generated_model_code_rejects_helper_solver():
    code = """
import json
import pyomo.environ as pyo
model = pyo.ConcreteModel()
model.SOURCES = pyo.Set(initialize=["a", "b"])
model.mass_kg = pyo.Var(model.SOURCES, bounds=(0, None))
model.objective = pyo.Objective(expr=sum(model.mass_kg[s] for s in model.SOURCES))
model.constraint = pyo.Constraint(expr=sum(model.mass_kg[s] for s in model.SOURCES) >= 1)
solver = pyo.SolverFactory("glpk")
from app.general_blend_domain_solver import solve_general_blend_spec
print("RESULT_JSON_START")
print(json.dumps({"solver_status": "ok"}))
print("RESULT_JSON_END")
"""

    errors = codegen.validate_generated_model_code(code)

    assert any("forbidden" in error for error in errors)


def test_generate_scaffold_guided_model_code_with_mocked_llm(monkeypatch, tmp_path):
    generated = """
import json
import pyomo.environ as pyo

SPEC = {
    "product_mass_kg": 1.0,
    "sources": [
        {"name": "a", "cost_per_kg": 1.0, "qualities": {"q": 0.1}},
        {"name": "b", "cost_per_kg": 2.0, "qualities": {"q": 0.2}},
    ],
}
SOLVER_NAME = "glpk"

source_lookup = {source["name"]: source for source in SPEC["sources"]}

model = pyo.ConcreteModel()
model.SOURCES = pyo.Set(initialize=list(source_lookup.keys()))

def source_bounds(model, source_name):
    return (0, None)

model.mass_kg = pyo.Var(model.SOURCES, bounds=source_bounds)
model.objective = pyo.Objective(
    expr=sum(source_lookup[source_name]["cost_per_kg"] * model.mass_kg[source_name] for source_name in model.SOURCES)
)
model.constraint = pyo.Constraint(expr=sum(model.mass_kg[source_name] for source_name in model.SOURCES) >= 1)
solver = pyo.SolverFactory(SOLVER_NAME)

result = {"solver_status": "ok"}

print("RESULT_JSON_START")
print(json.dumps(result, indent=2, sort_keys=True))
print("RESULT_JSON_END")
"""

    def fake_call_llm_text(system_prompt, user_prompt):
        return generated

    monkeypatch.setattr(codegen.llm_client, "call_llm_text", fake_call_llm_text)

    code = codegen.generate_scaffold_guided_model_code(
        prompt="make a blend",
        spec={
            "problem_type": "general_blend_cost_optimization",
            "product_mass_kg": 1.0,
            "objective": "minimize_cost",
            "sources": [
                {"name": "a", "cost_per_kg": 1.0, "qualities": {"q": 0.1}},
                {"name": "b", "cost_per_kg": 2.0, "qualities": {"q": 0.2}},
            ],
            "quality_upper_bounds": {"q": 0.2},
        },
        trace_dir=tmp_path,
    )

    assert "ConcreteModel" in code
    assert "model.mass_kg" in code
    assert (tmp_path / "codegen_trace.json").exists()


def test_validate_generated_model_code_rejects_undefined_source_expression():
    code = """
import json
import pyomo.environ as pyo

model = pyo.ConcreteModel()
model.SOURCES = pyo.Set(initialize=[\"a\", \"b\"])
model.mass_kg = pyo.Var(model.SOURCES, bounds=(0, None))
model.objective = pyo.Objective(
    expr=sum(source[\"cost_per_kg\"] * model.mass_kg[source_name] for source_name in model.SOURCES)
)
model.constraint = pyo.Constraint(expr=sum(model.mass_kg[s] for s in model.SOURCES) >= 1)
solver = pyo.SolverFactory(\"glpk\")

result = {\"solver_status\": \"ok\"}
print(\"RESULT_JSON_START\")
print(json.dumps(result, indent=2, sort_keys=True))
print(\"RESULT_JSON_END\")
"""

    errors = codegen.validate_generated_model_code(code)

    assert any("source_lookup[source_name]" in error for error in errors)
