from app.repair import extract_python_code, validate_patched_code


def test_extract_python_fenced_code():
    text = """```python
print("hello")
```"""
    assert extract_python_code(text) == 'print("hello")\n'


def test_extract_raw_code():
    text = 'print("hello")'
    assert extract_python_code(text) == 'print("hello")\n'


def test_validate_patched_code_accepts_minimal_generated_shape():
    code = """
import json
import traceback
import pyomo.environ as pyo

def build_model(spec):
    pass

def extract_results(model, spec):
    pass

def main():
    print("RESULT_JSON_START")
    print("{}")
    print("RESULT_JSON_END")
"""

    validate_patched_code(code)


def test_choose_safe_patch_repairs_pyomox_import_without_trusting_candidate():
    from app.repair import choose_safe_patch

    original_code = "import json\nimport traceback\nimport pyomox.environ as pyo\n"
    candidate_code = "print('bad candidate without pyomo import')"

    patched_code, strategy = choose_safe_patch(
        original_code=original_code,
        candidate_code=candidate_code,
        stdout="",
        stderr="ModuleNotFoundError: No module named pyomox"
    )

    assert "import pyomo.environ as pyo" in patched_code
    assert "import pyomox.environ as pyo" not in patched_code
    assert strategy == "minimal_import_patch_deterministic"
