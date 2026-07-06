# IDAES Agent MVP

Autonomous process-modeling agent MVP for small deterministic process-engineering problems.

The system takes a natural-language prompt and runs this loop:

Prompt -> structured spec -> scaffold code generation -> execution -> parsing -> engineering verification -> report -> storage.

This is not yet a full IDAES thermodynamic flowsheet agent. It is a controlled architecture MVP that proves the autonomous loop on simple process-modeling families.

## Current Capabilities

### 1. Heater/Cooler Energy Balance

Equation:

Q = m_dot * Cp * (T_out - T_in)

Supported modes:

1. calculate_heat_duty
2. calculate_outlet_temperature
3. calculate_mass_flow

Example prompts:

- Heat water from 300 K to 350 K at 1 bar and report heat duty.
- Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?
- I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?

### 2. Adiabatic Two-Stream Mixer

Equation:

T_out = (m1 Cp1 T1 + m2 Cp2 T2) / (m1 Cp1 + m2 Cp2)

Example prompt:

- Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?

Expected outlet temperature:

340 K

## Architecture

Natural-language prompt
-> Planner
-> Structured specification
-> Deterministic unit reconciliation
-> Registry validation
-> Scaffold-based code generation
-> Execution
-> RESULT_JSON parsing
-> Engineering verification
-> SQLite storage
-> Markdown report

## Design Choices

- The LLM helps with interpretation and repair suggestions.
- The backend owns validation, unit reconciliation, execution, parsing, verification, storage, and reporting.
- Generated code is written only inside run directories.
- Repair is constrained and does not blindly trust full LLM rewrites.
- Verification checks engineering balances, not just whether code ran.

## Setup

Create and activate the environment:

conda create -n idaes_agent python=3.11 -y
conda activate idaes_agent

Install dependencies:

pip install -r requirements.txt

Install IDAES extensions if needed:

idaes get-extensions

This MVP does not require IPOPT for the current examples because the scaffold models are solved directly.

## LLM Setup

This project currently uses Ollama.

Example .env:

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct

Make sure Ollama is running before LLM-planned heater runs.

## Run Examples

Heater heat duty:

python scripts/run_problem.py --planner llm "Heat water from 300 K to 350 K at 1 bar and report heat duty."

Expected:

heat_duty_w = 209200 W

Heater outlet temperature:

python scripts/run_problem.py --planner llm "Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?"

Expected:

temperature_out_k around 323.9006 K

Heater mass flow:

python scripts/run_problem.py --planner llm "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?"

Expected:

mass_flow_kg_s around 0.43456 kg/s

Adiabatic mixer:

python scripts/run_problem.py --planner llm "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?"

Expected:

outlet_temperature_k = 340 K

## Full Demo

Run:

python scripts/demo_all.py

It runs:

1. Heater heat-duty case
2. Heater outlet-temperature case
3. Heater mass-flow case
4. Adiabatic mixer case
5. Controlled repair smoke case

Expected:

passed: true
total_cases: 5
passed_cases: 5
failed_cases: 0

## Benchmark Suite

Run:

python scripts/run_benchmark.py --planner llm

Expected current result:

11/11 passed

## Repair Smoke Test

Run:

python scripts/run_repair_smoke.py

This intentionally injects a bad import into a generated model and verifies that the repair loop fixes it.

Expected:

passed: true
repair_attempts_used: 1
patch_strategy: minimal_import_patch_deterministic

## Test Suite

Run:

python -m pytest -q

Expected current result:

29 passed

Full health check:

python -m pytest -q
python scripts/run_benchmark.py --planner llm
python scripts/run_repair_smoke.py
python scripts/demo_all.py

## Output Structure

Runtime outputs are ignored by Git and written under:

outputs/

Each run gets its own directory:

outputs/runs/<run_id>/

Typical artifacts:

input.json
structured_spec.json
generated_model.py
raw_output.txt
parsed_result.json
verification.json
report.md
planner_trace.json

## Current Limitations

The current system does not yet support:

- Flash calculations
- VLE
- Reactors
- Distillation
- Optimization
- Multi-unit flowsheets
- Real thermodynamic property packages
- Dynamic simulation

The current physics are intentionally simple. The main achievement is the autonomous modeling architecture.

## Suggested Next Steps

Near-term:

1. Add a README demo transcript.
2. Add a third problem family, such as splitter mass balance.
3. Add stronger natural-language parsing for mixer prompts.
4. Add family-specific repair cases beyond bad imports.
5. Add a simple CLI interface.

Longer-term:

1. Add real IDAES unit models.
2. Add property package selection.
3. Add flowsheet-level composition handling.
4. Add optimization problems.
5. Add retrieval over example models and IDAES documentation.
