# Pyomo Patterns for General Blend Optimization

Use a ConcreteModel.

Create a source set from source names.

Create nonnegative source amount variables.

Use bounds when source minimum or maximum amounts are present.

Objective

sum(cost[source] * mass[source] for source in SOURCES)

Mass balance

sum(mass[source] for source in SOURCES) == product_mass

Quality upper bound

sum(quality[source, q] * mass[source] for source in SOURCES) <= upper_bound[q] * product_mass

Quality lower bound

sum(quality[source, q] * mass[source] for source in SOURCES) >= lower_bound[q] * product_mass

Result JSON should include

- problem_type
- mode
- backend
- solver_status
- termination_condition
- product_mass_kg
- total_blended_mass_kg
- total_cost
- mass_balance_residual_kg
- source_results
- quality_results
- quality_lower_bounds
- quality_upper_bounds
- quality_lower_slacks
- quality_upper_slacks
- maximum_quality_lower_violation
- maximum_quality_upper_violation

Source result fields

- name
- mass_kg
- cost_per_kg
- cost
- qualities
- min_required_kg
- max_available_kg
- minimum_usage_slack_kg
- availability_slack_kg
