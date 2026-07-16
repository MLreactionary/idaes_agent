
import pytest

from app.general_blend_domain_solver import solve_general_blend_spec


def test_animal_feed_blend_domain_solver():
    spec = {
        "problem_type": "general_blend_cost_optimization",
        "product_mass_kg": 1000,
        "objective": "minimize_cost",
        "sources": [
            {
                "name": "corn",
                "cost_per_kg": 0.30,
                "qualities": {
                    "protein": 0.09,
                    "fiber": 0.02
                }
            },
            {
                "name": "soybean_meal",
                "cost_per_kg": 0.90,
                "qualities": {
                    "protein": 0.50,
                    "fiber": 0.08
                }
            }
        ],
        "quality_lower_bounds": {
            "protein": 0.22
        },
        "quality_upper_bounds": {
            "fiber": 0.05
        }
    }

    result = solve_general_blend_spec(spec)

    assert result["solver_status"] == "ok"
    assert result["termination_condition"] == "optimal"
    assert result["total_blended_mass_kg"] == pytest.approx(1000.0)
    assert result["total_cost"] == pytest.approx(490.243902439, abs=1e-6)
    assert result["quality_results"]["protein"] == pytest.approx(0.22, abs=1e-8)
    assert result["quality_results"]["fiber"] <= 0.05 + 1e-8
    assert result["maximum_quality_lower_violation"] <= 1e-8
    assert result["maximum_quality_upper_violation"] <= 1e-8

    masses = {
        source["name"]: source["mass_kg"]
        for source in result["source_results"]
    }

    assert masses["corn"] == pytest.approx(682.926829268, abs=1e-6)
    assert masses["soybean_meal"] == pytest.approx(317.073170732, abs=1e-6)


def test_quality_lower_bound_infeasible():
    spec = {
        "problem_type": "general_blend_cost_optimization",
        "product_mass_kg": 100,
        "objective": "minimize_cost",
        "sources": [
            {
                "name": "low_grade_a",
                "cost_per_kg": 1.0,
                "qualities": {
                    "purity": 0.50
                }
            },
            {
                "name": "low_grade_b",
                "cost_per_kg": 2.0,
                "qualities": {
                    "purity": 0.60
                }
            }
        ],
        "quality_lower_bounds": {
            "purity": 0.95
        }
    }

    result = solve_general_blend_spec(spec)

    assert result["solver_status"] == "infeasible"
    assert "infeasibility_diagnosis" in result
    assert any(
        "lower bound" in reason
        for reason in result["infeasibility_diagnosis"]["reasons"]
    )
