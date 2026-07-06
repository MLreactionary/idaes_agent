import json
from pathlib import Path


class ReportError(Exception):
    pass


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise ReportError(f"Missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _fmt_bool(value) -> str:
    return "PASS" if value else "FAIL"


def _format_assumptions(spec: dict) -> list[str]:
    assumptions = []

    if spec.get("material") == "water":
        assumptions.append("Material was assumed to be water.")

    if spec.get("mass_flow_kg_s") == 1.0:
        if spec.get("mode") == "calculate_mass_flow":
            assumptions.append("Mass flow rate was solved from heat duty, heat capacity, and temperature change.")
        else:
            assumptions.append("Mass flow rate was assumed to be 1.0 kg/s if not explicitly specified.")

    if spec.get("cp_j_kg_k") == 4184.0:
        assumptions.append("Constant heat capacity was assumed as 4184 J/kg/K.")

    if spec.get("pressure_pa") == 100000.0:
        assumptions.append("Pressure was assumed or normalized to 100000 Pa.")

    assumptions.append("This MVP uses a sensible-heat energy balance and does not perform real thermodynamic property calculations.")

    return assumptions


def generate_report(
    run_id: str,
    original_prompt: str,
    run_dir: Path
) -> Path:
    run_dir = Path(run_dir)

    structured_spec_path = run_dir / "structured_spec.json"
    parsed_result_path = run_dir / "parsed_result.json"
    verification_path = run_dir / "verification.json"
    generated_model_path = run_dir / "generated_model.py"
    raw_output_path = run_dir / "raw_output.txt"
    explanation_path = run_dir / "llm_engineering_explanation.md"

    spec = _load_json(structured_spec_path)
    result = _load_json(parsed_result_path)
    verification = _load_json(verification_path)

    report_path = run_dir / "report.md"

    heat_duty_w = result.get("heat_duty_w")
    heat_duty_kw = heat_duty_w / 1000.0 if isinstance(heat_duty_w, (int, float)) else None

    lines = []

    lines.append("# Process Modeling Run Report")
    lines.append("")
    lines.append(f"**Run ID:** `{run_id}`")
    lines.append("")
    lines.append("## Original Prompt")
    lines.append("")
    lines.append(original_prompt)
    lines.append("")

    lines.append("## Supported Problem Type")
    lines.append("")
    lines.append(f"- Problem type: `{spec.get('problem_type')}`")
    lines.append(f"- Mode: `{spec.get('mode')}`")
    lines.append(f"- Backend: `{result.get('backend')}`")
    lines.append("")

    lines.append("## Model Used")
    lines.append("")
    lines.append("This run used the MVP heater/cooler sensible-heat energy balance:")
    lines.append("")
    lines.append("```text")
    lines.append("Q = m_dot * Cp * (T_out - T_in)")
    lines.append("```")
    lines.append("")
    lines.append("This is a controlled first benchmark model, not a full IDAES thermodynamic flowsheet.")
    lines.append("")

    lines.append("## Structured Specification")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(spec, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")

    lines.append("## Assumptions and Defaults")
    lines.append("")
    for assumption in _format_assumptions(spec):
        lines.append(f"- {assumption}")
    lines.append("")

    lines.append("## Execution Result")
    lines.append("")
    lines.append(f"- Solver/status method: `{result.get('solver_name')}`")
    lines.append(f"- Solver status: `{result.get('solver_status')}`")
    lines.append(f"- Termination condition: `{result.get('termination_condition')}`")
    lines.append(f"- Thermal direction: `{result.get('thermal_direction')}`")
    lines.append("")

    lines.append("## Engineering Result")
    lines.append("")
    lines.append(f"- Mass flow rate: `{result.get('mass_flow_kg_s')}` kg/s")
    lines.append(f"- Heat capacity: `{result.get('cp_j_kg_k')}` J/kg/K")
    lines.append(f"- Inlet temperature: `{result.get('temperature_in_k')}` K")
    lines.append(f"- Outlet temperature: `{result.get('temperature_out_k')}` K")
    lines.append(f"- Heat duty: `{result.get('heat_duty_w')}` W")
    if heat_duty_kw is not None:
        lines.append(f"- Heat duty: `{heat_duty_kw}` kW")
    lines.append(f"- Energy balance residual: `{result.get('energy_balance_residual_w')}` W")
    lines.append("")

    if explanation_path.exists():
        lines.append("## LLM Engineering Explanation")
        lines.append("")
        lines.append(explanation_path.read_text(encoding="utf-8").strip())
        lines.append("")
        lines.append("> This explanation was generated only after deterministic verification passed. It does not determine correctness.")
        lines.append("")

    lines.append("## Verification Summary")
    lines.append("")
    lines.append(f"- Verified: `{verification.get('verified')}`")
    lines.append(f"- Number of checks: `{verification.get('num_checks')}`")
    lines.append(f"- Number of failures: `{verification.get('num_failures')}`")
    lines.append("")

    lines.append("## Verification Checks")
    lines.append("")
    lines.append("| Check | Status | Message |")
    lines.append("|---|---:|---|")

    for check in verification.get("checks", []):
        name = check.get("name")
        passed = _fmt_bool(check.get("passed"))
        message = check.get("message", "").replace("\n", " ")
        lines.append(f"| `{name}` | {passed} | {message} |")

    lines.append("")

    if verification.get("failures"):
        lines.append("## Verification Failures")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(verification.get("failures"), indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")

    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- Structured spec: `{structured_spec_path}`")
    lines.append(f"- Generated model: `{generated_model_path}`")
    lines.append(f"- Raw output: `{raw_output_path}`")
    lines.append(f"- Parsed result: `{parsed_result_path}`")
    lines.append(f"- Verification: `{verification_path}`")
    if explanation_path.exists():
        lines.append(f"- LLM engineering explanation: `{explanation_path}`")
    lines.append(f"- Report: `{report_path}`")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path


if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[1]
    run_id = "codegen_test"
    run_dir = project_root / "outputs" / "runs" / run_id

    report_path = generate_report(
        run_id=run_id,
        original_prompt="Heat a water stream from 300 K to 350 K at 1 bar and report heat duty.",
        run_dir=run_dir
    )

    print("Report generated")
    print(f"report_path: {report_path}")
