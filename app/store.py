import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "outputs" / "db" / "runs.sqlite"


class StoreError(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """
    Initialize SQLite tables.

    This is deterministic storage only.
    The LLM should never decide database state.
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                original_prompt TEXT,
                problem_type TEXT,
                mode TEXT,

                status TEXT NOT NULL,
                verified INTEGER,
                num_failures INTEGER,

                run_dir TEXT,
                structured_spec_path TEXT,
                generated_code_path TEXT,
                raw_output_path TEXT,
                parsed_result_path TEXT,
                verification_path TEXT,
                report_path TEXT,

                error_message TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS repair_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                attempt_index INTEGER NOT NULL,
                created_at TEXT NOT NULL,

                failure_type TEXT,
                message TEXT,
                patch_summary TEXT,

                FOREIGN KEY(run_id) REFERENCES runs(run_id)
            )
            """
        )

        conn.commit()


def upsert_run(
    run_id: str,
    status: str,
    original_prompt: str | None = None,
    problem_type: str | None = None,
    mode: str | None = None,
    verified: bool | None = None,
    num_failures: int | None = None,
    run_dir: Path | str | None = None,
    structured_spec_path: Path | str | None = None,
    generated_code_path: Path | str | None = None,
    raw_output_path: Path | str | None = None,
    parsed_result_path: Path | str | None = None,
    verification_path: Path | str | None = None,
    report_path: Path | str | None = None,
    error_message: str | None = None,
    db_path: Path = DEFAULT_DB_PATH
) -> None:
    """
    Insert or update a run row.
    """
    init_db(db_path)

    now = utc_now_iso()

    def as_str(value):
        return str(value) if value is not None else None

    verified_int = None if verified is None else int(bool(verified))

    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT run_id, created_at FROM runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO runs (
                    run_id, created_at, updated_at,
                    original_prompt, problem_type, mode,
                    status, verified, num_failures,
                    run_dir, structured_spec_path, generated_code_path,
                    raw_output_path, parsed_result_path, verification_path,
                    report_path, error_message
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id, now, now,
                    original_prompt, problem_type, mode,
                    status, verified_int, num_failures,
                    as_str(run_dir),
                    as_str(structured_spec_path),
                    as_str(generated_code_path),
                    as_str(raw_output_path),
                    as_str(parsed_result_path),
                    as_str(verification_path),
                    as_str(report_path),
                    error_message
                )
            )
        else:
            conn.execute(
                """
                UPDATE runs
                SET
                    updated_at = ?,
                    original_prompt = COALESCE(?, original_prompt),
                    problem_type = COALESCE(?, problem_type),
                    mode = COALESCE(?, mode),
                    status = ?,
                    verified = COALESCE(?, verified),
                    num_failures = COALESCE(?, num_failures),
                    run_dir = COALESCE(?, run_dir),
                    structured_spec_path = COALESCE(?, structured_spec_path),
                    generated_code_path = COALESCE(?, generated_code_path),
                    raw_output_path = COALESCE(?, raw_output_path),
                    parsed_result_path = COALESCE(?, parsed_result_path),
                    verification_path = COALESCE(?, verification_path),
                    report_path = COALESCE(?, report_path),
                    error_message = COALESCE(?, error_message)
                WHERE run_id = ?
                """,
                (
                    now,
                    original_prompt,
                    problem_type,
                    mode,
                    status,
                    verified_int,
                    num_failures,
                    as_str(run_dir),
                    as_str(structured_spec_path),
                    as_str(generated_code_path),
                    as_str(raw_output_path),
                    as_str(parsed_result_path),
                    as_str(verification_path),
                    as_str(report_path),
                    error_message,
                    run_id
                )
            )

        conn.commit()


def record_run_from_files(
    run_id: str,
    original_prompt: str,
    run_dir: Path,
    db_path: Path = DEFAULT_DB_PATH
) -> None:
    """
    Record a completed run by reading structured_spec.json and verification.json.

    This keeps storage deterministic:
    - spec comes from structured_spec.json
    - verified status comes from verification.json
    """
    run_dir = Path(run_dir)

    structured_spec_path = run_dir / "structured_spec.json"
    generated_code_path = run_dir / "generated_model.py"
    raw_output_path = run_dir / "raw_output.txt"
    parsed_result_path = run_dir / "parsed_result.json"
    verification_path = run_dir / "verification.json"
    report_path = run_dir / "report.md"

    if not structured_spec_path.exists():
        raise StoreError(f"Missing structured spec: {structured_spec_path}")

    spec = json.loads(structured_spec_path.read_text(encoding="utf-8"))

    problem_type = spec.get("problem_type")
    mode = spec.get("mode")

    verified = None
    num_failures = None
    status = "unknown"

    if verification_path.exists():
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
        verified = bool(verification.get("verified", False))
        num_failures = int(verification.get("num_failures", 0))
        status = "verified" if verified else "failed_verification"
    elif parsed_result_path.exists():
        status = "parsed"
    elif raw_output_path.exists():
        status = "executed"
    elif generated_code_path.exists():
        status = "generated"

    upsert_run(
        run_id=run_id,
        original_prompt=original_prompt,
        problem_type=problem_type,
        mode=mode,
        status=status,
        verified=verified,
        num_failures=num_failures,
        run_dir=run_dir,
        structured_spec_path=structured_spec_path if structured_spec_path.exists() else None,
        generated_code_path=generated_code_path if generated_code_path.exists() else None,
        raw_output_path=raw_output_path if raw_output_path.exists() else None,
        parsed_result_path=parsed_result_path if parsed_result_path.exists() else None,
        verification_path=verification_path if verification_path.exists() else None,
        report_path=report_path if report_path.exists() else None,
        db_path=db_path
    )


def record_repair_attempt(
    run_id: str,
    attempt_index: int,
    failure_type: str,
    message: str,
    patch_summary: str | None = None,
    db_path: Path = DEFAULT_DB_PATH
) -> None:
    init_db(db_path)

    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO repair_attempts (
                run_id, attempt_index, created_at,
                failure_type, message, patch_summary
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                attempt_index,
                utc_now_iso(),
                failure_type,
                message,
                patch_summary
            )
        )
        conn.commit()


def list_runs(limit: int = 20, db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    init_db(db_path)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT
                run_id, created_at, updated_at,
                original_prompt, problem_type, mode,
                status, verified, num_failures,
                run_dir, report_path
            FROM runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    return [dict(row) for row in rows]


def get_run(run_id: str, db_path: Path = DEFAULT_DB_PATH) -> dict | None:
    init_db(db_path)

    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE run_id = ?",
            (run_id,)
        ).fetchone()

    return dict(row) if row else None


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    run_id = "codegen_test"
    run_dir = project_root / "outputs" / "runs" / run_id

    record_run_from_files(
        run_id=run_id,
        original_prompt="Heat a water stream from 300 K to 350 K at 1 bar and report heat duty.",
        run_dir=run_dir
    )

    print("Stored run in SQLite")
    print(json.dumps(get_run(run_id), indent=2))
