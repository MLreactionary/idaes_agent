# Capability Summary

## Agent loop

Prompt -> structured specification -> registry validation -> scaffold code generation -> execution -> RESULT_JSON parsing -> deterministic verification -> optional repair -> Markdown report -> SQLite storage.

## Supported families

| Family | Type | Method |
|---|---|---|
| heater_energy_balance | process calculation | direct equation |
| adiabatic_mixer | process calculation | direct equation |
| splitter_mass_balance | process calculation | direct equation |
| blend_cost_optimization | linear optimization | GLPK |
| general_blend_cost_optimization | linear optimization | GLPK |
| utility_emissions_optimization | linear optimization | GLPK |

## Verification

The verifier checks required fields, problem type, mode, solver status, termination condition, numeric finiteness, registry ranges, balances, objective consistency, quality feasibility, and emissions feasibility.

## Repair coverage

| Bug type | Repair strategy |
|---|---|
| bad_import | minimal_import_patch_deterministic |
| splitter_wrong_split_key | minimal_splitter_key_patch_deterministic |
| utility_wrong_emissions_key | minimal_utility_emissions_key_patch_deterministic |

## IDAES status

The optional IDAES backend currently provides a heater smoke path using an IDAES FlowsheetBlock. It is not yet a full thermodynamic property-package solve.
