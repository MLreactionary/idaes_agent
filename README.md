# IDAES Agent

Autonomous process-modeling agent that converts natural-language process-engineering tasks into executable, verified Pyomo and IDAES-style models.

## Current status

Expected health check.

```text
pytest: 43 passed
benchmark: 15/15 passed
demo: 9/9 passed
```

## Supported families

Process calculations:

- heater_energy_balance
- adiabatic_mixer
- splitter_mass_balance

Optimization families:

- blend_cost_optimization
- general_blend_cost_optimization
- utility_emissions_optimization

Backend support:

- direct Pyomo scaffold backend
- GLPK-backed linear optimization
- optional IDAES heater backend smoke path

## Quick run

```bash
python -m pytest -q
python scripts/run_benchmark.py --planner llm
python scripts/demo_all.py
```

## Repair coverage

Controlled repair cases:

- bad_import
- splitter_wrong_split_key
- utility_wrong_emissions_key

## Reports

Each run writes a Markdown report under outputs/runs/<run_id>/report.md with selected family, backend, equations, variables, objective, constraints, solver result, verification checks, artifact paths, and repair history when applicable.

## Example artifacts

Static generated examples are available under `examples/`.

They include a demo summary, benchmark summary, and representative paper-grade reports for heater, blend optimization, utility emissions optimization, and utility repair.

## Current limitations

Not yet supported:

- flash calculations
- VLE
- reactors
- distillation
- arbitrary multi-unit flowsheets
- real property-package-backed IDAES solves
- nonlinear optimization
- mixed-integer process synthesis
- dynamic simulation

See docs/capability_summary.md, docs/demo_commands.md, and docs/current_status.md.
