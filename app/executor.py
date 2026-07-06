import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExecutionResult:
    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    raw_output_path: Path


class ExecutorError(Exception):
    pass


def execute_model(model_path: Path, run_dir: Path, timeout_seconds: int = 30) -> ExecutionResult:
    """
    Execute generated_model.py in a subprocess.

    Responsibilities:
    - use the current Python environment
    - capture stdout
    - capture stderr
    - enforce timeout
    - write raw_output.txt

    This function does not parse RESULT_JSON.
    Parsing is handled separately by parser.py.
    """
    model_path = Path(model_path)
    run_dir = Path(run_dir)

    if not model_path.exists():
        raise ExecutorError(f"Model file does not exist: {model_path}")

    run_dir.mkdir(parents=True, exist_ok=True)
    raw_output_path = run_dir / "raw_output.txt"

    try:
        completed = subprocess.run(
            [sys.executable, str(model_path)],
            cwd=str(run_dir),
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )

        stdout = completed.stdout
        stderr = completed.stderr
        return_code = completed.returncode
        timed_out = False

    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        return_code = -1
        timed_out = True

    raw_text = []
    raw_text.append("=== EXECUTION METADATA ===")
    raw_text.append(f"model_path: {model_path}")
    raw_text.append(f"return_code: {return_code}")
    raw_text.append(f"timed_out: {timed_out}")
    raw_text.append("")
    raw_text.append("=== STDOUT ===")
    raw_text.append(stdout)
    raw_text.append("")
    raw_text.append("=== STDERR ===")
    raw_text.append(stderr)

    raw_output_path.write_text("\n".join(raw_text), encoding="utf-8")

    return ExecutionResult(
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        raw_output_path=raw_output_path
    )


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    run_dir = project_root / "outputs" / "runs" / "codegen_test"
    model_path = run_dir / "generated_model.py"

    result = execute_model(model_path=model_path, run_dir=run_dir)

    print("Execution complete")
    print(f"return_code: {result.return_code}")
    print(f"timed_out: {result.timed_out}")
    print(f"raw_output_path: {result.raw_output_path}")
