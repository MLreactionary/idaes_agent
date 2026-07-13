
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_problem import run_problem


EXAMPLES = {
    "Heater or cooler": [
        "Heat a water stream from 300 K to 350 K at 1 bar and report heat duty.",
        "Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?",
        "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?",
    ],
    "Adiabatic mixer": [
        "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?",
        "Blend 3600 kg/hr of water at 25 C with 0.5 kg/s of water at 75 C. What is the outlet temperature?",
    ],
    "Two-source blend optimization": [
        "Optimize a blend of 100 kg product using source A cost 2 $/kg impurity 1% and source B cost 1 $/kg impurity 5%, with final impurity limit 3%. What is the minimum cost blend?",
    ],
    "General blend optimization": [
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost.",
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2% max 40 kg, source B cost 1 $/kg sulfur 5% ash 1% max 30 kg, and source C cost 1.5 $/kg sulfur 2% ash 3% max 100 kg. Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost.",
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2% minimum 50 kg, source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost.",
    ],
    "General blend infeasibility": [
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2% max 20 kg, source B cost 1 $/kg sulfur 5% ash 1% max 20 kg, and source C cost 1.5 $/kg sulfur 2% ash 3% max 20 kg. Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost.",
        "Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 5% ash 2%, source B cost 1 $/kg sulfur 6% ash 1%, and source C cost 1.5 $/kg sulfur 7% ash 3%. Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost.",
    ],
    "Utility emissions optimization": [
        "A process needs 500 kW of heat for 1 hr. Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. Emissions must be at most 60 kg CO2/hr. Minimize cost.",
    ],
    "Power plant dispatch": [
        "An electric utility company must meet a fixed community demand of 500 kW during a peak hour. Coal Plant min 100 kW max 400 kW cost 25 $/kWh emissions 0.95 kg CO2/kWh. Gas Plant min 50 kW max 300 kW cost 15 $/kWh emissions 0.45 kg CO2/kWh. Biomass Plant min 10 kW max 80 kW cost 7 $/kWh emissions 0.05 kg CO2/kWh. Minimize total operating cost.",
    ],
    "Utility emissions sweep": [
        "A process needs 500 kW of heat for 1 hr. Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. Sweep emissions caps from 40 to 100 kg CO2/hr in 20 kg steps and report the cost emissions tradeoff.",
    ],
    "Multi-period utility planning": [
        "Period 1 needs 500 kW of heat for 1 hr, period 2 needs 300 kW of heat for 1 hr. Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. Total emissions must be at most 100 kg CO2. Minimize cost.",
    ],
    "IDAES heater backend": [
        "Heat a water stream from 300 K to 350 K at 1 bar and report heat duty.",
        "Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?",
        "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?",
    ],
}


def load_json(path: Path):
    if not path.exists():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def load_text(path: Path):
    if not path.exists():
        return None

    return path.read_text(encoding="utf-8")


def show_json(label: str, data):
    st.subheader(label)

    if data is None:
        st.info("Not available for this run.")
    else:
        st.json(data)


def as_table(rows):
    if not rows:
        return None
    return pd.DataFrame(rows)


def show_result_tables(result: dict):
    if not result:
        return

    problem_type = result.get("problem_type")
    mode = result.get("mode")

    if problem_type == "general_blend_cost_optimization":
        if result.get("solver_status") == "infeasible":
            st.warning("The optimization problem was diagnosed as infeasible.")
            diagnosis = result.get("infeasibility_diagnosis", {})
            for reason in diagnosis.get("reasons", []):
                st.write("- " + str(reason))
            return

        source_df = as_table(result.get("source_results", []))
        if source_df is not None:
            st.markdown("#### Source decisions")
            st.dataframe(source_df, use_container_width=True)

        quality_rows = []
        quality_results = result.get("quality_results", {})
        quality_limits = result.get("quality_limits", {})
        quality_slacks = result.get("quality_slacks", {})

        for quality_name in sorted(quality_limits):
            quality_rows.append(
                {
                    "quality": quality_name,
                    "result": quality_results.get(quality_name),
                    "limit": quality_limits.get(quality_name),
                    "slack": quality_slacks.get(quality_name),
                }
            )

        if quality_rows:
            st.markdown("#### Quality results")
            st.dataframe(pd.DataFrame(quality_rows), use_container_width=True)

    elif problem_type == "utility_emissions_optimization" and mode == "sweep_emissions_cap":
        sweep_df = as_table(result.get("sweep_results", []))
        if sweep_df is not None:
            st.markdown("#### Cost-emissions sweep")
            st.dataframe(sweep_df, use_container_width=True)

    elif problem_type == "utility_emissions_optimization" and mode == "multi_period_minimize_cost_with_emissions_cap":
        period_df = as_table(result.get("period_results", []))
        if period_df is not None:
            st.markdown("#### Period summary")
            clean_period_df = period_df.drop(columns=["utility_results"], errors="ignore")
            st.dataframe(clean_period_df, use_container_width=True)

        utility_rows = []
        for period in result.get("period_results", []):
            for utility in period.get("utility_results", []):
                row = dict(utility)
                row["period"] = period.get("name")
                utility_rows.append(row)

        if utility_rows:
            st.markdown("#### Period utility decisions")
            st.dataframe(pd.DataFrame(utility_rows), use_container_width=True)

    elif problem_type == "utility_emissions_optimization":
        utility_df = as_table(result.get("utility_results", []))
        if utility_df is not None:
            st.markdown("#### Utility decisions")
            st.dataframe(utility_df, use_container_width=True)

    elif problem_type == "blend_cost_optimization":
        rows = [
            {
                "source": result.get("source1_name"),
                "mass_kg": result.get("source1_mass_kg"),
            },
            {
                "source": result.get("source2_name"),
                "mass_kg": result.get("source2_mass_kg"),
            },
        ]
        st.markdown("#### Source decisions")
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


def show_key_metrics(run_result: dict, parsed_result: dict, verification: dict):
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Run status", run_result.get("status", "unknown"))

    with col2:
        st.metric("Verified", str(run_result.get("verified", False)))

    with col3:
        st.metric("Failures", run_result.get("num_failures", "N/A"))

    with col4:
        st.metric("Problem type", parsed_result.get("problem_type", "N/A") if parsed_result else "N/A")

    if parsed_result:
        st.markdown("#### Main outputs")

        metric_cols = st.columns(4)
        candidates = [
            ("Mode", parsed_result.get("mode")),
            ("Backend", parsed_result.get("backend")),
            ("Total cost", parsed_result.get("total_cost")),
            ("Heat duty W", parsed_result.get("heat_duty_w")),
            ("Outlet T K", parsed_result.get("temperature_out_k")),
            ("Mass flow kg/s", parsed_result.get("mass_flow_kg_s")),
            ("Total emissions", parsed_result.get("total_emissions_kg_co2")),
            ("Solver status", parsed_result.get("solver_status")),
        ]

        shown = 0
        for label, value in candidates:
            if value is not None and shown < 4:
                with metric_cols[shown]:
                    st.metric(label, value)
                shown += 1


def render_run(run_result: dict):
    run_dir = Path(run_result["run_dir"])

    model_selection = load_json(run_dir / "model_selection_trace.json")
    planner_trace = load_json(run_dir / "planner_trace.json")
    spec = load_json(run_dir / "structured_spec.json")
    parsed_result = load_json(run_dir / "parsed_result.json")
    verification = load_json(run_dir / "verification.json")
    report = load_text(run_dir / "report.md")
    generated_model = load_text(run_dir / "generated_model.py")
    raw_output = load_text(run_dir / "raw_output.txt")

    show_key_metrics(run_result, parsed_result or {}, verification or {})

    st.divider()

    tabs = st.tabs(
        [
            "Result",
            "Report",
            "Model selection",
            "Structured spec",
            "Verification",
            "Generated code",
            "Artifacts",
            "Raw output",
        ]
    )

    with tabs[0]:
        show_result_tables(parsed_result or {})
        show_json("Parsed RESULT_JSON", parsed_result)

    with tabs[1]:
        if report:
            st.markdown(report)
        else:
            st.info("Report not found.")

    with tabs[2]:
        show_json("Model selection trace", model_selection)
        show_json("Planner trace", planner_trace)

    with tabs[3]:
        show_json("Structured specification", spec)

    with tabs[4]:
        show_json("Verification", verification)

    with tabs[5]:
        if generated_model:
            st.code(generated_model, language="python")
        else:
            st.info("Generated model not found.")

    with tabs[6]:
        artifact_rows = []
        for name in [
            "input.json",
            "model_selection_trace.json",
            "planner_trace.json",
            "structured_spec.json",
            "generated_model.py",
            "raw_output.txt",
            "parsed_result.json",
            "verification.json",
            "report.md",
        ]:
            path = run_dir / name
            artifact_rows.append(
                {
                    "artifact": name,
                    "exists": path.exists(),
                    "path": str(path),
                }
            )

        st.dataframe(pd.DataFrame(artifact_rows), use_container_width=True)

    with tabs[7]:
        if raw_output:
            st.code(raw_output)
        else:
            st.info("Raw output not found.")


def main():
    st.set_page_config(
        page_title="IDAES Agent Demo",
        layout="wide",
    )

    st.title("IDAES Agent")
    st.caption("Natural language prompt to scaffolded Pyomo or IDAES-backed model execution, verification, and report.")

    with st.sidebar:
        st.header("Run configuration")

        category = st.selectbox("Capability category", list(EXAMPLES.keys()))
        example = st.selectbox("Example prompt", EXAMPLES[category])

        default_backend = "idaes" if category == "IDAES heater backend" else "default"
        backend_choice = st.selectbox(
            "Backend",
            ["default", "pyomo", "idaes"],
            index=["default", "pyomo", "idaes"].index(default_backend),
        )

        planner = st.selectbox("Planner", ["llm", "regex"], index=0)

        st.markdown("---")
        st.markdown("Current benchmark target")
        st.write("26/26 passing cases")

    prompt = st.text_area("Prompt", value=example, height=140)

    col1, col2 = st.columns([1, 5])

    with col1:
        run_clicked = st.button("Run agent", type="primary", use_container_width=True)

    with col2:
        st.info("Pick any category or edit the prompt. The run will create a fresh output directory under outputs/runs.")

    if run_clicked:
        backend = None if backend_choice == "default" else backend_choice

        with st.spinner("Running agent pipeline..."):
            try:
                run_result = run_problem(
                    prompt=prompt,
                    planner=planner,
                    explain=False,
                    repair=False,
                    inject_bug=False,
                    max_repair_attempts=0,
                    backend=backend,
                )

                st.session_state["last_run_result"] = run_result

            except Exception as exc:
                st.error(f"Run failed: {type(exc).__name__}: {exc}")
                st.stop()

    if "last_run_result" in st.session_state:
        st.success("Latest run loaded.")
        render_run(st.session_state["last_run_result"])
    else:
        st.markdown("### What this UI shows")
        st.write(
            "Choose a benchmarked capability, run the agent, and inspect the selected model family, "
            "structured spec, generated code, parsed result, verification, and Markdown report."
        )


if __name__ == "__main__":
    main()
