import pytest

from app.parser import extract_result_json_from_text, ParserError


def test_extract_valid_result_json():
    text = """
some logs
RESULT_JSON_START
{"solver_status": "ok", "heat_duty_w": 100.0}
RESULT_JSON_END
more logs
"""

    result = extract_result_json_from_text(text)

    assert result["solver_status"] == "ok"
    assert result["heat_duty_w"] == 100.0


def test_missing_start_marker_fails():
    text = """
{"solver_status": "ok"}
RESULT_JSON_END
"""

    with pytest.raises(ParserError):
        extract_result_json_from_text(text)


def test_missing_end_marker_fails():
    text = """
RESULT_JSON_START
{"solver_status": "ok"}
"""

    with pytest.raises(ParserError):
        extract_result_json_from_text(text)


def test_invalid_json_fails():
    text = """
RESULT_JSON_START
{"solver_status": "ok",
RESULT_JSON_END
"""

    with pytest.raises(ParserError):
        extract_result_json_from_text(text)
