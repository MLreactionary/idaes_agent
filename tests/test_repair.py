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
