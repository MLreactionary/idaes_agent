import json
from pathlib import Path


def load_json(path: Path):
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def build_repair_history_markdown(run_dir: Path) -> str:
    run_dir = Path(run_dir)

    injected_bug_path = run_dir / "injected_bug.json"
    repair_trace_paths = sorted(run_dir.glob("repair_attempt_*_trace.json"))

    if not injected_bug_path.exists() and not repair_trace_paths:
        return ""

    lines = []
    lines.append("## Repair History")
    lines.append("")

    injected_bug = load_json(injected_bug_path)

    if injected_bug:
        lines.append("### Injected Bug")
        lines.append("")
        lines.append(f"- Bug type: `{injected_bug.get('bug_type', 'unknown')}`")
        lines.append(f"- Description: {injected_bug.get('description', 'N/A')}")
        lines.append(f"- Target: `{injected_bug.get('target', 'N/A')}`")
        lines.append(f"- Replacement: `{injected_bug.get('replacement', 'N/A')}`")
        lines.append("")

    if repair_trace_paths:
        lines.append("### Repair Attempts")
        lines.append("")

        for trace_path in repair_trace_paths:
            trace = load_json(trace_path)

            if not trace:
                continue

            attempt_index = trace.get("attempt_index", "unknown")
            patch_strategy = trace.get("patch_strategy", "unknown")
            failure_return_code = trace.get("failure_return_code", "unknown")
            failure_timed_out = trace.get("failure_timed_out", "unknown")
            llm = trace.get("llm", {})

            provider = llm.get("provider", "unknown")
            model = llm.get("model", "unknown")

            lines.append(f"#### Attempt {attempt_index}")
            lines.append("")
            lines.append(f"- Failure return code: `{failure_return_code}`")
            lines.append(f"- Timed out: `{failure_timed_out}`")
            lines.append(f"- LLM provider: `{provider}`")
            lines.append(f"- LLM model: `{model}`")
            lines.append(f"- Patch strategy: `{patch_strategy}`")
            lines.append(f"- Trace file: `{trace_path.name}`")
            lines.append("")

    verification = load_json(run_dir / "verification.json")

    if verification:
        lines.append("### Final Verification")
        lines.append("")
        lines.append(f"- Verified: `{verification.get('verified', 'unknown')}`")
        lines.append(f"- Number of failures: `{verification.get('num_failures', 'unknown')}`")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def append_repair_history_to_report(run_dir: Path, report_path: Path) -> Path:
    run_dir = Path(run_dir)
    report_path = Path(report_path)

    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")

    repair_markdown = build_repair_history_markdown(run_dir)

    if not repair_markdown.strip():
        return report_path

    report_text = report_path.read_text(encoding="utf-8")

    if "## Repair History" in report_text:
        return report_path

    updated_report = report_text.rstrip() + "\n\n" + repair_markdown
    report_path.write_text(updated_report, encoding="utf-8")

    return report_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("report_path")
    args = parser.parse_args()

    append_repair_history_to_report(
        run_dir=Path(args.run_dir),
        report_path=Path(args.report_path)
    )
