from app.llm_planner import extract_json_object


def test_extract_raw_json():
    text = '{"problem_type": "heater_energy_balance"}'
    result = extract_json_object(text)
    assert result["problem_type"] == "heater_energy_balance"


def test_extract_fenced_json():
    text = """```json
{
  "status": "success",
  "backend": "ollama"
}
```"""
    result = extract_json_object(text)
    assert result["status"] == "success"
    assert result["backend"] == "ollama"


def test_extract_json_with_extra_text():
    text = """
Here is the JSON:
{
  "mode": "calculate_heat_duty"
}
Done.
"""
    result = extract_json_object(text)
    assert result["mode"] == "calculate_heat_duty"
