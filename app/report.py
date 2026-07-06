import json
from pathlib import Path


def load_json(path: Path):
    path = Path(path)

    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def format_value(value):
    if value is None:
        return "N/A"

    return str(value)


def build_model_overview(spec: dict) -> list[str]:
    problem_type = spec.get("problem_type")

    lines = []
    lines.append("## Model Overview")
    lines.append("")

    if problem_type == "heater_energy_balance":
        lines.append("This run used the MVP heater/cooler sensible-heat energy balance:")
        lines.append("")
        lines.append("```text")
        lines.append("Q = m_dot * Cp * (T_out - T_in)")
        lines.append("```")
        lines.append("")
        lines.append(
            "This is a controlled first benchmark model, not a full IDAES thermodynamic flowsheet."
        )

    elif problem_type == "adiabatic_mixer":
        lines.append("This run used the MVP adiabatic two-stream mixer energy balance:")
        lines.append("")
        lines.append("```text")
        lines.append("T_out = (m1 Cp1 T1 + m2 Cp2 T2) / (m1 Cp1 + m2 Cp2)")
        lines.append("```")
        lines.append("")
        lines.append(
            "This is a controlled mixer benchmark model. It assumes adiabatic mixing, constant heat capacities, and no phase change."
        )

    else:
        lines.append(f"This run used problem type `{problem_type}`.")
        lines.append("")
        lines.append("No family-specific model overview is available yet.")

    return lines


def build_assumptions(spec: dict) -> list[str]:
    problem_type = spec.get("problem_type")

    lines = []
    lines.append("## Assumptions and Defaults")
    lines.append("")

    if problem_type == "heater_energy_balance":
        lines.append("- Material was assumed to be water unless explicitly specified.")

        if spec.get("mode") == "calculate_mass_flow":
            lines.append(
                "- Mass flow rate was solved from heat duty, heat capacity, and temperature change."
            )
        else:
            lines.append(
                f"- Mass flow rate was assumed or parsed as {format_value(spec.get('mass_flow_kg_s'))} kg/s."
            )

        lines.append(
            f"- Constant heat capacity was assumed or parsed as {format_value(spec.get('cp_j_kg_k'))} J/kg/K."
        )
        lines.append(
            f"- Pressure was assumed or normalized to {format_value(spec.get('pressure_pa'))} Pa."
        )
        lines.append(
            "- This MVP uses a sensible-heat energy balance and does not perform real thermodynamic property calculations."
        )

    elif problem_type == "adiabatic_mixer":
        lines.append("- Material was assumed to be water unless explicitly specified.")
        lines.append("- The mixer is assumed adiabatic, with no heat loss to the surroundings.")
        lines.append("- No phase change, reaction, pressure drop, or real-fluid property calculation is modeled.")
        lines.append(
            f"- Stream 1 heat capacity was assumed or parsed as {format_value(spec.get('stream1_cp_j_kg_k'))} J/kg/K."
        )
        lines.append(
            f"- Stream 2 heat capacity was assumed or parsed as {format_value(spec.get('stream2_cp_j_kg_k'))} J/kg/K."
        )
        lines.append(
            f"- Pressure was assumed or normalized to {format_value(spec.get('pressure_pa'))} Pa."
        )

    else:
        lines.append("- No family-specific assumptions are available yet.")

    return lines


def build_execution_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Execution Result")
    lines.append("")
    lines.append(f"- Solver/status method: `{format_value(result.get('solver_name'))}`")
    lines.append(f"- Solver status: `{format_value(result.get('solver_status'))}`")
    lines.append(f"- Termination condition: `{format_value(result.get('termination_condition'))}`")

    if result.get("thermal_direction") is not None:
        lines.append(f"- Thermal direction: `{format_value(result.get('thermal_direction'))}`")

    return lines


def build_heater_engineering_result(result: dict) -> list[str]:
    heat_duty_w = result.get("heat_duty_w")
    heat_duty_kw = None

    if isinstance(heat_duty_w, (int, float)):
        heat_duty_kw = heat_duty_w / 1000.0

    lines = []
    lines.append("## Engineering Result")
    lines.append("")
    lines.append(f"- Mass flow rate: `{format_value(result.get('mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Heat capacity: `{format_value(result.get('cp_j_kg_k'))}` J/kg/K")
    lines.append(f"- Inlet temperature: `{format_value(result.get('temperature_in_k'))}` K")
    lines.append(f"- Outlet temperature: `{format_value(result.get('temperature_out_k'))}` K")
    lines.append(f"- Heat duty: `{format_value(heat_duty_w)}` W")

    if heat_duty_kw is not None:
        lines.append(f"- Heat duty: `{heat_duty_kw}` kW")

    lines.append(
        f"- Energy balance residual: `{format_value(result.get('energy_balance_residual_w'))}` W"
    )

    return lines


def build_mixer_engineering_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Engineering Result")
    lines.append("")

    lines.append("### Stream 1")
    lines.append("")
    lines.append(
        f"- Mass flow rate: `{format_value(result.get('stream1_mass_flow_kg_s'))}` kg/s"
    )
    lines.append(
        f"- Temperature: `{format_value(result.get('stream1_temperature_k'))}` K"
    )
    lines.append(
        f"- Heat capacity: `{format_value(result.get('stream1_cp_j_kg_k'))}` J/kg/K"
    )
    lines.append("")

    lines.append("### Stream 2")
    lines.append("")
    lines.append(
        f"- Mass flow rate: `{format_value(result.get('stream2_mass_flow_kg_s'))}` kg/s"
    )
    lines.append(
        f"- Temperature: `{format_value(result.get('stream2_temperature_k'))}` K"
    )
    lines.append(
        f"- Heat capacity: `{format_value(result.get('stream2_cp_j_kg_k'))}` J/kg/K"
    )
    lines.append("")

    lines.append("### Outlet")
    lines.append("")
    lines.append(
        f"- Outlet temperature: `{format_value(result.get('outlet_temperature_k'))}` K"
    )
    lines.append(
        f"- Outlet temperature alias: `{format_value(result.get('temperature_out_k'))}` K"
    )
    lines.append(
        f"- Energy balance residual: `{format_value(result.get('energy_balance_residual_w'))}` W"
    )

    return lines


def build_engineering_result(result: dict) -> list[str]:
    problem_type = result.get("problem_type")

    if problem_type == "heater_energy_balance":
        return build_heater_engineering_result(result)

    if problem_type == "adiabatic_mixer":
        return build_mixer_engineering_result(result)

    lines = []
    lines.append("## Engineering Result")
    lines.append("")
    lines.append("No family-specific engineering result renderer is available yet.")
    return lines


def build_llm_explanation(run_dir: Path) -> list[str]:
    explanation_path = Path(run_dir) / "llm_engineering_explanation.md"

    if not explanation_path.exists():
        return []

    explanation = explanation_path.read_text(encoding="utf-8").strip()

    if not explanation:
        return []

    lines = []
    lines.append("## LLM Engineering Explanation")
    lines.append("")
    lines.append(explanation)
    return lines


def build_verification_summary(verification: dict | None) -> list[str]:
    lines = []
    lines.append("## Verification Summary")
    lines.append("")

    if verification is None:
        lines.append("- Verification file was not found.")
        return lines

    lines.append(f"- Verified: `{format_value(verification.get('verified'))}`")
    lines.append(f"- Number of checks: `{format_value(verification.get('num_checks'))}`")
    lines.append(f"- Number of failures: `{format_value(verification.get('num_failures'))}`")

    checks = verification.get("checks", [])

    if checks:
        lines.append("")
        lines.append("## Verification Checks")
        lines.append("")
        lines.append("| Check | Status | Message |")
        lines.append("|---|---:|---|")

        for check in checks:
            status = "PASS" if check.get("passed") else "FAIL"
            lines.append(
                f"| `{check.get('name')}` | {status} | {check.get('message')} |"
            )

    return lines


def build_artifacts(run_dir: Path) -> list[str]:
    run_dir = Path(run_dir)

    artifact_files = [
        ("Structured spec", "structured_spec.json"),
        ("Generated model", "generated_model.py"),
        ("Raw output", "raw_output.txt"),
        ("Parsed result", "parsed_result.json"),
        ("Verification", "verification.json"),
        ("Report", "report.md"),
    ]

    lines = []
    lines.append("## Artifacts")
    lines.append("")

    for label, filename in artifact_files:
        path = run_dir / filename

        if path.exists():
            lines.append(f"- {label}: `{path}`")

    return lines


def generate_report(
    run_id: str,
    original_prompt: str,
    run_dir: Path
) -> Path:
    run_dir = Path(run_dir)

    spec = load_json(run_dir / "structured_spec.json") or {}
    result = load_json(run_dir / "parsed_result.json") or {}
    verification = load_json(run_dir / "verification.json")

    report_path = run_dir / "report.md"

    lines = []
    lines.append(f"# IDAES Agent Run Report: `{run_id}`")
    lines.append("")
    lines.append("## Original Prompt")
    lines.append("")
    lines.append(original_prompt)
    lines.append("")

    lines.extend(build_model_overview(spec))
    lines.append("")

    lines.append("## Structured Specification")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(spec, indent=2, sort_keys=True))
    lines.append("```")
    lines.append("")

    lines.extend(build_assumptions(spec))
    lines.append("")

    lines.extend(build_execution_result(result))
    lines.append("")

    lines.extend(build_engineering_result(result))
    lines.append("")

    explanation_lines = build_llm_explanation(run_dir)

    if explanation_lines:
        lines.extend(explanation_lines)
        lines.append("")

    lines.extend(build_verification_summary(verification))
    lines.append("")

    lines.extend(build_artifacts(run_dir))
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return report_path


if __name__ == "__main__":
    raise SystemExit("Use generate_report() from the run pipeline.")
