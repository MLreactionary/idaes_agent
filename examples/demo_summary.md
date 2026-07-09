# Demo Report: demo_20260708_215156

- Passed: `True`
- Total cases: `9`
- Passed cases: `9`
- Failed cases: `0`

## Cases

### heater_heat_duty — PASS

- Run ID: `run_20260708_215156_fdb3aa41`
- Report: `<repo>/outputs/runs/run_20260708_215156_fdb3aa41/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=heater_energy_balance
- `mode`: PASS — mode=calculate_heat_duty
- `heat_duty_w`: PASS — heat_duty_w=209200.0

### heater_outlet_temperature — PASS

- Run ID: `run_20260708_215208_ca1b0ceb`
- Report: `<repo>/outputs/runs/run_20260708_215208_ca1b0ceb/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=heater_energy_balance
- `mode`: PASS — mode=calculate_outlet_temperature
- `temperature_out_k`: PASS — temperature_out_k=323.9005736137667

### heater_mass_flow — PASS

- Run ID: `run_20260708_215218_47e8cb31`
- Report: `<repo>/outputs/runs/run_20260708_215218_47e8cb31/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=heater_energy_balance
- `mode`: PASS — mode=calculate_mass_flow
- `mass_flow_kg_s`: PASS — mass_flow_kg_s=0.4345558838866678

### adiabatic_mixer — PASS

- Run ID: `run_20260708_215230_b571bd56`
- Report: `<repo>/outputs/runs/run_20260708_215230_b571bd56/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=adiabatic_mixer
- `mode`: PASS — mode=calculate_outlet_temperature
- `temperature_out_k`: PASS — temperature_out_k=340.0

### blend_cost_optimization — PASS

- Run ID: `run_20260708_215230_5c9a980c`
- Report: `<repo>/outputs/runs/run_20260708_215230_5c9a980c/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=blend_cost_optimization
- `mode`: PASS — mode=minimize_cost
- `source1_mass_kg`: PASS — source1_mass_kg=50.0
- `source2_mass_kg`: PASS — source2_mass_kg=50.0
- `total_cost`: PASS — total_cost=150.0
- `final_impurity_fraction`: PASS — final_impurity_fraction=0.03

### general_blend_cost_optimization — PASS

- Run ID: `run_20260708_215231_783078e3`
- Report: `<repo>/outputs/runs/run_20260708_215231_783078e3/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=general_blend_cost_optimization
- `mode`: PASS — mode=minimize_cost
- `number_of_sources`: PASS — number_of_sources=3
- `total_mass_kg`: PASS — total_mass_kg=100.0
- `total_cost`: PASS — total_cost=140.0
- `maximum_quality_violation_fraction`: PASS — maximum_quality_violation_fraction=0.0

### utility_emissions_optimization — PASS

- Run ID: `run_20260708_215231_4a5e1f5b`
- Report: `<repo>/outputs/runs/run_20260708_215231_4a5e1f5b/report.md`

Checks:
- `verified`: PASS — verified=True
- `problem_type`: PASS — problem_type=utility_emissions_optimization
- `mode`: PASS — mode=minimize_cost_with_emissions_cap
- `number_of_utilities`: PASS — number_of_utilities=2
- `total_heat_kwh`: PASS — total_heat_kwh=500.0
- `total_cost`: PASS — total_cost=30.666666666666686
- `total_emissions_kg_co2`: PASS — total_emissions_kg_co2=59.99999999999995
- `emissions_violation_kg_co2`: PASS — emissions_violation_kg_co2=0.0

### controlled_repair_smoke — PASS

- Run ID: `run_20260708_215231_ed15ce78`
- Report: `<repo>/outputs/runs/run_20260708_215231_ed15ce78/report.md`

Checks:
- `verified`: PASS — verified=True
- `repair_attempts_used`: PASS — repair_attempts_used=1
- `patch_strategy`: PASS — patch_strategy=minimal_import_patch_deterministic
- `report_has_repair_history`: PASS — repair history present

### utility_optimization_repair_smoke — PASS

- Run ID: `run_20260708_215241_6bc3c420`
- Report: `<repo>/outputs/runs/run_20260708_215241_6bc3c420/report.md`

Checks:
- `verified`: PASS — verified=True
- `repair_attempts_used`: PASS — repair_attempts_used=1
- `patch_strategy`: PASS — patch_strategy=minimal_utility_emissions_key_patch_deterministic
- `problem_type`: PASS — problem_type=utility_emissions_optimization
- `total_cost`: PASS — total_cost=30.666666666666686
- `report_has_repair_history`: PASS — repair history present
