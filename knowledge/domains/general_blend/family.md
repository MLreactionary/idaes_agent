# General Blend Optimization Domain

This domain covers linear blending and formulation problems.

The core task is to choose amounts of input sources to produce a target product amount while minimizing cost and satisfying quality constraints.

Common real-world names for this family include animal feed formulation, fuel blending, ore blending, chemical purity blending, waste treatment blending, raw material formulation, and recipe optimization.

## Canonical formulation

Decision variable

x_i = amount of source i used

Objective

minimize sum_i cost_i * x_i

Mass balance

sum_i x_i = product_mass

Source bounds

source_min_i <= x_i <= source_max_i

Quality upper bound

sum_i quality_iq * x_i <= upper_q * product_mass

Quality lower bound

sum_i quality_iq * x_i >= lower_q * product_mass

## Important interpretation rules

Percent values must be converted to fractions.

9 percent protein becomes 0.09.

22 percent minimum protein becomes lower bound 0.22.

Fiber at most 5 percent becomes upper bound 0.05.

The scaffold should not care whether the quality is called protein, sulfur, ash, fiber, iron, octane, purity, or grade.

All of these are qualities.

## Supported variants

- any number of sources
- arbitrary source names
- arbitrary quality names
- quality lower bounds
- quality upper bounds
- source maximum availability
- source minimum required usage
- minimize total cost
- infeasibility diagnosis

## Out of scope

- nonlinear blending rules
- reactions
- phase equilibrium
- integer source selection
- scheduling
- dynamic models
- unknown objective functions
