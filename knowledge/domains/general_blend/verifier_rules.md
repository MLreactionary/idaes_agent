# Verifier Rules for General Blend Optimization

The verifier must recompute all engineering quantities from source results.

Required checks

1. Solver status is ok or infeasible.

2. If optimal, total source mass must match product mass.

3. Each source mass must be nonnegative.

4. Source minimum usage constraints must be satisfied.

5. Source maximum availability constraints must be satisfied.

6. Every upper-bound quality must satisfy actual_quality <= upper_bound.

7. Every lower-bound quality must satisfy actual_quality >= lower_bound.

8. Total cost must equal sum source mass times source cost.

9. All numeric values must be finite.

10. If infeasible, the result must include an infeasibility diagnosis.

Common infeasibility reasons

- total maximum availability is below product mass
- total minimum required usage is above product mass
- a source minimum exceeds its maximum
- a quality lower bound is above the best achievable quality
- a quality upper bound is below the best achievable quality
- lower and upper bounds conflict
