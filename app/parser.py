import json
from pathlib import Path


START_MARKER = "RESULT_JSON_START"
END_MARKER = "RESULT_JSON_END"


class ParserError(Exception):
    pass


def extract_result_json_from_text(text: str) -> dict:
    """
    Extract the JSON object printed between RESULT_JSON_START and RESULT_JSON_END.
    """

    if START_MARKER not in text:
        raise ParserError(f"Missing marker: {START_MARKER}")

    if END_MARKER not in text:
        raise ParserError(f"Missing marker: {END_MARKER}")

    start_index = text.index(START_MARKER) + len(START_MARKER)
    end_index = text.index(END_MARKER)

    json_text = text[start_index:end_index].strip()

    if not json_text:
        raise ParserError("RESULT_JSON block is empty")

    try:
        return json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ParserError(f"Invalid RESULT_JSON: {exc}") from exc


def parse_execution_result(stdout: str, run_dir: Path) -> Path:
    """
    Parse RESULT_JSON from executor stdout and write parsed_result.json.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    result = extract_result_json_from_text(stdout)

    parsed_result_path = run_dir / "parsed_result.json"
    parsed_result_path.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8"
    )

    return parsed_result_path


def parse_raw_output_file(raw_output_path: Path, run_dir: Path) -> Path:
    """
    Parse RESULT_JSON from raw_output.txt.

    This is useful when inspecting saved runs.
    """
    raw_output_path = Path(raw_output_path)

    if not raw_output_path.exists():
        raise ParserError(f"Raw output file not found: {raw_output_path}")

    text = raw_output_path.read_text(encoding="utf-8")
    return parse_execution_result(text, run_dir)


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    run_dir = project_root / "outputs" / "runs" / "codegen_test"
    raw_output_path = run_dir / "raw_output.txt"

    parsed_path = parse_raw_output_file(raw_output_path, run_dir)

    print("Parsing complete")
    print(f"parsed_result_path: {parsed_path}")
