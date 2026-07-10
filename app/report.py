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

    if isinstance(value, float):
        return f"{value:.10g}"

    return str(value)


def format_percent_fraction(value):
    if value is None:
        return "N/A"

    return f"{100.0 * float(value):.6g}%"


def build_model_selection_summary(run_dir: Path) -> list[str]:
    selection = load_json(Path(run_dir) / "model_selection_trace.json")

    if not selection:
        return []

    lines = []
    lines.append("## Model Selection Trace")
    lines.append("")
    lines.append(f"- Selector: `{format_value(selection.get('selector'))}`")
    lines.append(f"- Selected problem type: `{format_value(selection.get('selected_problem_type'))}`")
    lines.append(f"- Selected planner: `{format_value(selection.get('selected_planner_name'))}`")
    lines.append(f"- Selected score: `{format_value(selection.get('selected_score'))}`")

    candidates = selection.get("candidates", [])[:5]

    if candidates:
        lines.append("")
        lines.append("| Candidate problem type | Planner | Score |")
        lines.append("|---|---|---:|")

        for candidate in candidates:
            lines.append(
                f"| `{candidate.get('problem_type')}` | `{candidate.get('planner_name')}` | `{format_value(candidate.get('score'))}` |"
            )

    return lines


def build_model_overview(spec: dict) -> list[str]:
    problem_type = spec.get("problem_type")
    mode = spec.get("mode")
    backend = spec.get("backend", "pyomo")

    family_titles = {
        "heater_energy_balance": "Heater or cooler sensible-heat calculation",
        "adiabatic_mixer": "Adiabatic two-stream mixer calculation",
        "splitter_mass_balance": "Splitter mass-balance calculation",
        "blend_cost_optimization": "Two-source blend cost optimization",
        "general_blend_cost_optimization": "General blend cost optimization",
        "utility_emissions_optimization": "Utility cost and emissions optimization",
    }

    lines = []
    lines.append("## Model Overview")
    lines.append("")
    lines.append(f"- Selected family: `{problem_type}`")
    lines.append(f"- Family description: {family_titles.get(problem_type, 'Unknown or unsupported family')}")
    lines.append(f"- Mode: `{mode}`")
    lines.append(f"- Backend: `{backend}`")
    lines.append("")

    if problem_type == "heater_energy_balance":
        lines.append("The model applies a constant-Cp sensible-heat balance.")
        lines.append("")
        lines.append("```text")
        lines.append("Q = m_dot * Cp * (T_out - T_in)")
        lines.append("```")

    elif problem_type == "adiabatic_mixer":
        lines.append("The model applies an adiabatic two-stream mixing energy balance.")
        lines.append("")
        lines.append("```text")
        lines.append("T_out = (m1 Cp1 T1 + m2 Cp2 T2) / (m1 Cp1 + m2 Cp2)")
        lines.append("```")

    elif problem_type == "splitter_mass_balance":
        lines.append("The model splits an inlet mass flow into two outlet streams.")
        lines.append("")
        lines.append("```text")
        lines.append("outlet1 = split_fraction * inlet")
        lines.append("outlet2 = inlet - outlet1")
        lines.append("```")

    elif problem_type == "blend_cost_optimization":
        lines.append("The model solves a linear two-source blend optimization problem.")
        lines.append("")
        lines.append("```text")
        lines.append("minimize cost1*x1 + cost2*x2")
        lines.append("subject to x1 + x2 = product_mass")
        lines.append("           impurity1*x1 + impurity2*x2 <= impurity_limit*product_mass")
        lines.append("           x1, x2 >= 0")
        lines.append("```")

    elif problem_type == "general_blend_cost_optimization":
        lines.append("The model solves a linear blending optimization problem with multiple sources and quality limits.")
        lines.append("")
        lines.append("```text")
        lines.append("minimize sum_i cost_i * x_i")
        lines.append("subject to sum_i x_i = product_mass")
        lines.append("           sum_i quality_{i,k} * x_i <= limit_k * product_mass for each quality k")
        lines.append("           x_i >= 0")
        lines.append("```")

    elif problem_type == "utility_emissions_optimization":
        lines.append("The model chooses heating utility amounts to minimize cost while satisfying an emissions cap.")
        lines.append("")
        lines.append("```text")
        lines.append("minimize sum_u cost_u * heat_u")
        lines.append("subject to sum_u heat_u = heat_demand")
        lines.append("           sum_u emissions_u * heat_u <= emissions_cap")
        lines.append("           heat_u >= 0")
        lines.append("```")

    else:
        lines.append("No family-specific model overview is available yet.")

    return lines


def build_decision_model_summary(spec: dict) -> list[str]:
    problem_type = spec.get("problem_type")

    lines = []
    lines.append("## Decision Model Summary")
    lines.append("")

    if problem_type in {"heater_energy_balance", "adiabatic_mixer", "splitter_mass_balance"}:
        lines.append("- Model type: deterministic algebraic process calculation")
        lines.append("- Objective: not applicable")
        lines.append("- Solver role: direct calculation or simple equation evaluation")
        lines.append("- Decision variables: not applicable for this calculation family")
        return lines

    if problem_type == "blend_cost_optimization":
        lines.append("- Model type: linear program")
        lines.append("- Objective: minimize total source cost")
        lines.append("- Decision variables:")
        lines.append("  - `source1_mass_kg`")
        lines.append("  - `source2_mass_kg`")
        lines.append("- Constraints:")
        lines.append("  - product mass balance")
        lines.append("  - impurity upper bound")
        lines.append("  - nonnegative source masses")
        return lines

    if problem_type == "general_blend_cost_optimization":
        source_names = [source.get("name") for source in spec.get("sources", [])]
        quality_names = sorted((spec.get("quality_limits") or {}).keys())

        lines.append("- Model type: linear program")
        lines.append("- Objective: minimize total source cost")
        lines.append("- Decision variables:")
        for source_name in source_names:
            lines.append(f"  - `mass_kg[{source_name}]`")
        lines.append("- Constraints:")
        lines.append("  - product mass balance")
        for quality_name in quality_names:
            lines.append(f"  - `{quality_name}` upper bound")
        lines.append("  - nonnegative source masses")
        return lines

    if problem_type == "utility_emissions_optimization":
        utility_names = [utility.get("name") for utility in spec.get("utilities", [])]

        lines.append("- Model type: linear program")
        lines.append("- Objective: minimize total utility cost")
        lines.append("- Decision variables:")
        for utility_name in utility_names:
            lines.append(f"  - `heat_kwh[{utility_name}]`")
        lines.append("- Constraints:")
        lines.append("  - heat demand balance")
        lines.append("  - emissions cap")
        lines.append("  - nonnegative utility heat amounts")
        return lines

    lines.append("- No family-specific decision model summary is available yet.")
    return lines


def build_assumptions(spec: dict) -> list[str]:
    problem_type = spec.get("problem_type")

    lines = []
    lines.append("## Assumptions and Defaults")
    lines.append("")

    if problem_type == "heater_energy_balance":
        lines.append("- Material was assumed to be water unless explicitly specified.")
        lines.append(f"- Mass flow rate: `{format_value(spec.get('mass_flow_kg_s'))}` kg/s")
        lines.append(f"- Heat capacity: `{format_value(spec.get('cp_j_kg_k'))}` J/kg/K")
        lines.append(f"- Pressure: `{format_value(spec.get('pressure_pa'))}` Pa")
        lines.append("- Constant heat capacity and no phase change are assumed.")

    elif problem_type == "adiabatic_mixer":
        lines.append("- Material was assumed to be water unless explicitly specified.")
        lines.append("- The mixer is adiabatic.")
        lines.append("- Constant heat capacities are used.")
        lines.append("- No phase change, reaction, or pressure drop is modeled.")

    elif problem_type == "splitter_mass_balance":
        lines.append("- The splitter is modeled as a mass-only split.")
        lines.append("- No energy balance, pressure drop, or composition calculation is modeled.")

    elif problem_type == "blend_cost_optimization":
        lines.append("- Continuous source amounts are allowed.")
        lines.append("- Blending quality is linear in source mass.")
        lines.append("- There are no source availability bounds in this family yet.")

    elif problem_type == "general_blend_cost_optimization":
        lines.append("- Continuous source amounts are allowed.")
        lines.append("- Each quality attribute is blended linearly by mass.")
        lines.append("- Quality constraints are upper bounds.")
        lines.append("- There are no source availability bounds in this family yet.")

    elif problem_type == "utility_emissions_optimization":
        lines.append("- Utility heat contributions are continuous.")
        lines.append("- Cost and emissions are linear in supplied heat.")
        lines.append("- Heat demand is fixed.")
        lines.append("- Emissions cap is treated as an upper bound.")

    else:
        lines.append("- No family-specific assumptions are available yet.")

    return lines


def build_execution_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Execution Result")
    lines.append("")
    lines.append(f"- Solver or method: `{format_value(result.get('solver_name'))}`")
    lines.append(f"- Optimization solver: `{format_value(result.get('optimization_solver'))}`")
    lines.append(f"- Solver status: `{format_value(result.get('solver_status'))}`")
    lines.append(f"- Termination condition: `{format_value(result.get('termination_condition'))}`")

    if result.get("thermal_direction") is not None:
        lines.append(f"- Thermal direction: `{format_value(result.get('thermal_direction'))}`")

    return lines


def build_heater_engineering_result(result: dict) -> list[str]:
    heat_duty_w = result.get("heat_duty_w")
    heat_duty_kw = heat_duty_w / 1000.0 if isinstance(heat_duty_w, (int, float)) else None

    lines = []
    lines.append("## Engineering Result")
    lines.append("")
    lines.append(f"- Mass flow rate: `{format_value(result.get('mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Heat capacity: `{format_value(result.get('cp_j_kg_k'))}` J/kg/K")
    lines.append(f"- Inlet temperature: `{format_value(result.get('temperature_in_k'))}` K")
    lines.append(f"- Outlet temperature: `{format_value(result.get('temperature_out_k'))}` K")
    lines.append(f"- Heat duty: `{format_value(heat_duty_w)}` W")

    if heat_duty_kw is not None:
        lines.append(f"- Heat duty: `{format_value(heat_duty_kw)}` kW")

    lines.append(f"- Energy balance residual: `{format_value(result.get('energy_balance_residual_w'))}` W")

    if result.get("backend") == "idaes":
        lines.append("- IDAES FlowsheetBlock created: `" + format_value(result.get("idaes_flowsheet_block_created")) + "`")
        lines.append("- IDAES solver required: `" + format_value(result.get("idaes_solver_required")) + "`")

    return lines


def build_mixer_engineering_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Engineering Result")
    lines.append("")
    lines.append(f"- Stream 1 mass flow: `{format_value(result.get('stream1_mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Stream 1 temperature: `{format_value(result.get('stream1_temperature_k'))}` K")
    lines.append(f"- Stream 2 mass flow: `{format_value(result.get('stream2_mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Stream 2 temperature: `{format_value(result.get('stream2_temperature_k'))}` K")
    lines.append(f"- Outlet temperature: `{format_value(result.get('temperature_out_k'))}` K")
    lines.append(f"- Energy balance residual: `{format_value(result.get('energy_balance_residual_w'))}` W")
    return lines


def build_splitter_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Engineering Result")
    lines.append("")
    lines.append(f"- Inlet mass flow: `{format_value(result.get('inlet_mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Outlet 1 split fraction: `{format_value(result.get('outlet1_split_fraction'))}`")
    lines.append(f"- Outlet 1 mass flow: `{format_value(result.get('outlet1_mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Outlet 2 mass flow: `{format_value(result.get('outlet2_mass_flow_kg_s'))}` kg/s")
    lines.append(f"- Mass balance residual: `{format_value(result.get('mass_balance_residual_kg_s'))}` kg/s")
    return lines


def build_blend_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Optimization Result")
    lines.append("")
    lines.append(f"- Product mass: `{format_value(result.get('product_mass_kg'))}` kg")
    lines.append(f"- Source 1 `{format_value(result.get('source1_name'))}` mass: `{format_value(result.get('source1_mass_kg'))}` kg")
    lines.append(f"- Source 2 `{format_value(result.get('source2_name'))}` mass: `{format_value(result.get('source2_mass_kg'))}` kg")
    lines.append(f"- Final impurity: `{format_percent_fraction(result.get('final_impurity_fraction'))}`")
    lines.append(f"- Impurity limit: `{format_percent_fraction(result.get('impurity_limit_fraction'))}`")
    lines.append(f"- Total cost: `{format_value(result.get('total_cost'))}`")
    lines.append(f"- Mass balance residual: `{format_value(result.get('mass_balance_residual_kg'))}` kg")
    return lines


def build_general_blend_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Optimization Result")
    lines.append("")

    if result.get("solver_status") == "infeasible":
        lines.append("- Result status: `infeasible`")
        lines.append("- Termination condition: `" + format_value(result.get("termination_condition")) + "`")
        lines.append("- Product mass: `" + format_value(result.get("product_mass_kg")) + "` kg")
        lines.append("")
        lines.append("### Infeasibility Diagnosis")
        lines.append("")

        diagnosis = result.get("infeasibility_diagnosis", {})
        reasons = diagnosis.get("reasons", [])

        if reasons:
            for reason in reasons:
                lines.append("- " + str(reason))
        else:
            lines.append("- No diagnosis reasons were returned.")

        return lines

    lines.append("- Product mass: `" + format_value(result.get("product_mass_kg")) + "` kg")
    lines.append("- Total blended mass: `" + format_value(result.get("total_mass_kg")) + "` kg")
    lines.append("- Total cost: `" + format_value(result.get("total_cost")) + "`")
    lines.append("- Mass balance residual: `" + format_value(result.get("mass_balance_residual_kg")) + "` kg")
    lines.append("- Maximum quality violation: `" + format_value(result.get("maximum_quality_violation_fraction")) + "`")
    lines.append("- Maximum source availability violation: `" + format_value(result.get("maximum_source_availability_violation_kg")) + "` kg")
    lines.append("- Maximum minimum usage violation: `" + format_value(result.get("maximum_minimum_usage_violation_kg")) + "` kg")
    lines.append("")
    lines.append("### Source Decisions")
    lines.append("")
    lines.append("| Source | Mass kg | Cost per kg | Max available kg | Availability slack kg | Min required kg | Minimum slack kg |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")

    for source in result.get("source_results", []):
        lines.append(
            "| `" + format_value(source.get("name")) + "` | `" +
            format_value(source.get("mass_kg")) + "` | `" +
            format_value(source.get("cost_per_kg")) + "` | `" +
            format_value(source.get("max_available_kg")) + "` | `" +
            format_value(source.get("availability_slack_kg")) + "` | `" +
            format_value(source.get("min_required_kg")) + "` | `" +
            format_value(source.get("minimum_usage_slack_kg")) + "` |"
        )

    lines.append("")
    lines.append("### Quality Results")
    lines.append("")
    lines.append("| Quality | Result | Limit | Slack |")
    lines.append("|---|---:|---:|---:|")

    quality_results = result.get("quality_results", {})
    quality_limits = result.get("quality_limits", {})
    quality_slacks = result.get("quality_slacks", {})

    for quality_name in sorted(quality_limits):
        lines.append(
            "| `" + str(quality_name) + "` | `" +
            format_percent_fraction(quality_results.get(quality_name)) + "` | `" +
            format_percent_fraction(quality_limits.get(quality_name)) + "` | `" +
            format_value(quality_slacks.get(quality_name)) + "` |"
        )

    return lines


def build_single_period_utility_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Optimization Result")
    lines.append("")
    lines.append("- Heat demand: `" + format_value(result.get("heat_demand_kwh")) + "` kWh")
    lines.append("- Total heat supplied: `" + format_value(result.get("total_heat_kwh")) + "` kWh")
    lines.append("- Total cost: `" + format_value(result.get("total_cost")) + "`")
    lines.append("- Total emissions: `" + format_value(result.get("total_emissions_kg_co2")) + "` kg CO2")
    lines.append("- Emissions cap: `" + format_value(result.get("emissions_cap_kg_co2")) + "` kg CO2")
    lines.append("- Emissions violation: `" + format_value(result.get("emissions_violation_kg_co2")) + "` kg CO2")
    lines.append("")
    lines.append("### Utility Decisions")
    lines.append("")
    lines.append("| Utility | Heat kWh | Cost | Emissions kg CO2 |")
    lines.append("|---|---:|---:|---:|")

    for utility in result.get("utility_results", []):
        lines.append(
            "| `" + format_value(utility.get("name")) + "` | `" +
            format_value(utility.get("heat_kwh")) + "` | `" +
            format_value(utility.get("cost")) + "` | `" +
            format_value(utility.get("emissions_kg_co2")) + "` |"
        )

    return lines


def build_utility_sweep_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Optimization Result")
    lines.append("")
    lines.append("- Mode: `emissions cap sweep`")
    lines.append("- Heat demand: `" + format_value(result.get("heat_demand_kwh")) + "` kWh")
    lines.append("- Number of sweep points: `" + format_value(result.get("number_of_sweep_points")) + "`")
    lines.append("- Minimum total cost: `" + format_value(result.get("minimum_total_cost")) + "`")
    lines.append("- Maximum total cost: `" + format_value(result.get("maximum_total_cost")) + "`")
    lines.append("- Maximum emissions violation: `" + format_value(result.get("maximum_emissions_violation_kg_co2")) + "` kg CO2")
    lines.append("")
    lines.append("### Cost and Emissions Tradeoff")
    lines.append("")
    lines.append("| Emissions cap kg CO2 | Status | Total cost | Total emissions kg CO2 | Emissions violation kg CO2 |")
    lines.append("|---:|---|---:|---:|---:|")

    for point in result.get("sweep_results", []):
        lines.append(
            "| `" + format_value(point.get("emissions_cap_kg_co2")) + "` | `" +
            format_value(point.get("sweep_point_status")) + "` | `" +
            format_value(point.get("total_cost")) + "` | `" +
            format_value(point.get("total_emissions_kg_co2")) + "` | `" +
            format_value(point.get("emissions_violation_kg_co2")) + "` |"
        )

    return lines


def build_multi_period_utility_result(result: dict) -> list[str]:
    lines = []
    lines.append("## Optimization Result")
    lines.append("")
    lines.append("- Mode: `multi-period emissions-constrained utility planning`")
    lines.append("- Number of periods: `" + format_value(result.get("number_of_periods")) + "`")
    lines.append("- Number of utilities: `" + format_value(result.get("number_of_utilities")) + "`")
    lines.append("- Total heat demand: `" + format_value(result.get("total_heat_demand_kwh")) + "` kWh")
    lines.append("- Total heat supplied: `" + format_value(result.get("total_heat_kwh")) + "` kWh")
    lines.append("- Total cost: `" + format_value(result.get("total_cost")) + "`")
    lines.append("- Total emissions: `" + format_value(result.get("total_emissions_kg_co2")) + "` kg CO2")
    lines.append("- Total emissions cap: `" + format_value(result.get("total_emissions_cap_kg_co2")) + "` kg CO2")
    lines.append("- Emissions violation: `" + format_value(result.get("emissions_violation_kg_co2")) + "` kg CO2")
    lines.append("- Maximum period heat residual: `" + format_value(result.get("maximum_period_heat_balance_residual_kwh")) + "` kWh")
    lines.append("")
    lines.append("### Period Summary")
    lines.append("")
    lines.append("| Period | Heat demand kWh | Heat supplied kWh | Cost | Emissions kg CO2 | Heat residual kWh |")
    lines.append("|---|---:|---:|---:|---:|---:|")

    for period in result.get("period_results", []):
        lines.append(
            "| `" + format_value(period.get("name")) + "` | `" +
            format_value(period.get("heat_demand_kwh")) + "` | `" +
            format_value(period.get("total_heat_kwh")) + "` | `" +
            format_value(period.get("total_cost")) + "` | `" +
            format_value(period.get("total_emissions_kg_co2")) + "` | `" +
            format_value(period.get("heat_balance_residual_kwh")) + "` |"
        )

    lines.append("")
    lines.append("### Period Utility Decisions")
    lines.append("")
    lines.append("| Period | Utility | Heat kWh | Cost | Emissions kg CO2 |")
    lines.append("|---|---|---:|---:|---:|")

    for period in result.get("period_results", []):
        for utility in period.get("utility_results", []):
            lines.append(
                "| `" + format_value(period.get("name")) + "` | `" +
                format_value(utility.get("name")) + "` | `" +
                format_value(utility.get("heat_kwh")) + "` | `" +
                format_value(utility.get("cost")) + "` | `" +
                format_value(utility.get("emissions_kg_co2")) + "` |"
            )

    return lines


def build_utility_result(result: dict) -> list[str]:
    mode = result.get("mode")

    if mode == "sweep_emissions_cap":
        return build_utility_sweep_result(result)

    if mode == "multi_period_minimize_cost_with_emissions_cap":
        return build_multi_period_utility_result(result)

    return build_single_period_utility_result(result)


def build_engineering_result(result: dict) -> list[str]:
    problem_type = result.get("problem_type")

    if problem_type == "heater_energy_balance":
        return build_heater_engineering_result(result)

    if problem_type == "adiabatic_mixer":
        return build_mixer_engineering_result(result)

    if problem_type == "splitter_mass_balance":
        return build_splitter_result(result)

    if problem_type == "blend_cost_optimization":
        return build_blend_result(result)

    if problem_type == "general_blend_cost_optimization":
        return build_general_blend_result(result)

    if problem_type == "utility_emissions_optimization":
        return build_utility_result(result)

    lines = []
    lines.append("## Engineering Result")
    lines.append("")
    lines.append("No family-specific result renderer is available yet.")
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
            message = str(check.get("message", "")).replace("|", "\\|")
            lines.append(f"| `{check.get('name')}` | {status} | {message} |")

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


def generate_report(run_id: str, original_prompt: str, run_dir: Path) -> Path:
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

    model_selection_lines = build_model_selection_summary(run_dir)

    if model_selection_lines:
        lines.extend(model_selection_lines)
        lines.append("")

    lines.extend(build_model_overview(spec))
    lines.append("")

    lines.extend(build_decision_model_summary(spec))
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
