# Benchmark Report: benchmark_20260708_214828

- Planner: `llm`
- Total cases: `15`
- Passed cases: `15`
- Failed cases: `0`

## Cases

### heat_kelvin_default_flow — PASS

- Outcome: `passed`
- Prompt: Heat a water stream from 300 K to 350 K at 1 bar and report heat duty.
- Run ID: `run_20260708_214828_63dfd5ca`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_214828_63dfd5ca/report.md`

### heat_celsius_default_flow — PASS

- Outcome: `passed`
- Prompt: I have water at 27 C and I want to heat it to 77 C at 1 bar. What heat duty is needed?
- Run ID: `run_20260708_214848_2f8ef2ef`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_214848_2f8ef2ef/report.md`

### cool_celsius_with_flow — PASS

- Outcome: `passed`
- Prompt: Cool water from 80 C to 30 C at 2 kg/s and report the heat duty.
- Run ID: `run_20260708_214906_cbac6285`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_214906_cbac6285/report.md`

### heat_kelvin_with_flow — PASS

- Outcome: `passed`
- Prompt: Heat water from 300 K to 330 K at 3 kg/s. Report the heat duty.
- Run ID: `run_20260708_214925_8494f851`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_214925_8494f851/report.md`

### outlet_temperature_from_heat_duty — PASS

- Outcome: `passed`
- Prompt: Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?
- Run ID: `run_20260708_214932_404471b9`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_214932_404471b9/report.md`

### outlet_temperature_with_heat_removed — PASS

- Outcome: `passed`
- Prompt: Water enters at 350 K and 50 kW of heat is removed. What is the outlet temperature?
- Run ID: `run_20260708_214958_6446b4a3`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_214958_6446b4a3/report.md`

### heat_rich_units_kg_hr_kj_cp — PASS

- Outcome: `passed`
- Prompt: Heat 3600 kg/hr of water from 25 C to 80 C at 101.325 kPa using Cp = 4.18 kJ/kg/K. Report heat duty.
- Run ID: `run_20260708_215014_ddcba825`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215014_ddcba825/report.md`

### mass_flow_from_heat_duty_and_temperature_rise — PASS

- Outcome: `passed`
- Prompt: I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?
- Run ID: `run_20260708_215055_06031560`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215055_06031560/report.md`

### adiabatic_mixer_two_water_streams — PASS

- Outcome: `passed`
- Prompt: Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?
- Run ID: `run_20260708_215107_1738a069`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215107_1738a069/report.md`

### unsupported_flash — PASS

- Outcome: `expected_error`
- Prompt: Flash a methane ethane mixture at 300 K and 1 bar and report vapor fraction.
- Error: `flash is not supported`

### unsupported_reactor — PASS

- Outcome: `expected_error`
- Prompt: Model a reactor converting A to B with first-order kinetics.
- Error: `The prompt is unsupported as it involves reaction kinetics, which is not currently supported by the provided scope.`

### adiabatic_mixer_rich_units_celsius_kg_hr — PASS

- Outcome: `passed`
- Prompt: Blend 3600 kg/hr of water at 25 C with 0.5 kg/s of water at 75 C. What is the outlet temperature?
- Run ID: `run_20260708_215155_ed925044`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215155_ed925044/report.md`

### blend_cost_optimization_two_sources — PASS

- Outcome: `passed`
- Prompt: Optimize a blend of 100 kg product using source A cost 2 $/kg impurity 1% and source B cost 1 $/kg impurity 5%, with final impurity limit 3%. What is the minimum cost blend?
- Run ID: `run_20260708_215155_a0371482`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215155_a0371482/report.md`

### general_blend_cost_optimization_three_sources — PASS

- Outcome: `passed`
- Prompt: Optimize a blend of 100 kg product using source A cost 2 $/kg sulfur 1% ash 2%, source B cost 1 $/kg sulfur 5% ash 1%, and source C cost 1.5 $/kg sulfur 2% ash 3%. Final sulfur must be at most 3% and ash must be at most 2%. Minimize cost.
- Run ID: `run_20260708_215156_16d7dc4a`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215156_16d7dc4a/report.md`

### utility_emissions_optimization — PASS

- Outcome: `passed`
- Prompt: A process needs 500 kW of heat for 1 hr. Steam cost 0.04 $/kWh emissions 0.2 kg CO2/kWh, and electric heat cost 0.08 $/kWh emissions 0.05 kg CO2/kWh. Emissions must be at most 60 kg CO2/hr. Minimize cost.
- Run ID: `run_20260708_215156_f8efddb9`
- Verified: `True`
- Report: `<repo>/outputs/runs/run_20260708_215156_f8efddb9/report.md`
