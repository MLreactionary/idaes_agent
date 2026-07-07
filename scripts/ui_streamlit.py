import json
import sys
from pathlib import Path

import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


st.set_page_config(
    page_title="IDAES Agent MVP",
    page_icon="⚙️",
    layout="wide"
)

st.title("IDAES Agent MVP")
st.caption("Prompt → spec → generated model → execution → verification → report")

examples = [
    "Heat water from 300 K to 350 K at 1 bar and report heat duty.",
    "Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?",
    "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?",
    "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?",
    "Blend 3600 kg/hr of water at 25 C with 0.5 kg/s of water at 75 C. What is the outlet temperature?",
    "Split 10 kg/s of water with 30% going to outlet 1. What are the outlet flows?"
]

example = st.selectbox("Example prompts", examples)

prompt = st.text_area(
    "Prompt",
    value=example,
    height=120
)

col1, col2, col3 = st.columns(3)

with col1:
    planner = st.selectbox("Planner", ["llm", "regex"], index=0)

with col2:
    repair = st.checkbox("Enable repair", value=False)

with col3:
    explain = st.checkbox("Generate explanation", value=False)

run_button = st.button("Run agent", type="primary")

if run_button:
    if not prompt.strip():
        st.error("Enter a prompt first.")
        st.stop()

    with st.spinner("Running agent..."):
        try:
            result = run_problem(
                prompt=prompt,
                planner=planner,
                explain=explain,
                repair=repair,
                inject_bug=False,
                max_repair_attempts=1
            )
        except Exception as exc:
            st.error(f"Run failed: {type(exc).__name__}: {exc}")
            st.stop()

    st.success("Run complete")

    st.subheader("Run Summary")
    st.json(result)

    run_dir = Path(result["run_dir"])

    parsed_path = run_dir / "parsed_result.json"
    verification_path = run_dir / "verification.json"
    spec_path = run_dir / "structured_spec.json"
    report_path = run_dir / "report.md"

    tab1, tab2, tab3, tab4 = st.tabs(
        ["Parsed Result", "Verification", "Structured Spec", "Report"]
    )

    with tab1:
        if parsed_path.exists():
            st.json(json.loads(parsed_path.read_text()))
        else:
            st.warning("parsed_result.json not found.")

    with tab2:
        if verification_path.exists():
            st.json(json.loads(verification_path.read_text()))
        else:
            st.warning("verification.json not found.")

    with tab3:
        if spec_path.exists():
            st.json(json.loads(spec_path.read_text()))
        else:
            st.warning("structured_spec.json not found.")

    with tab4:
        if report_path.exists():
            st.markdown(report_path.read_text())
        else:
            st.warning("report.md not found.")

st.divider()

st.subheader("Supported MVP Families")
st.markdown(
    """
- `heater_energy_balance`
  - `calculate_heat_duty`
  - `calculate_outlet_temperature`
  - `calculate_mass_flow`
- `adiabatic_mixer`
  - `calculate_outlet_temperature`
- `splitter_mass_balance`
  - `calculate_outlet_flows`
"""
)
