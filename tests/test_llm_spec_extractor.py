
import json

import pytest

import app.llm_spec_extractor as extractor


ANIMAL_FEED_PROMPT = (
    "We need to produce exactly 1,000 kg of animal feed. "
    "Corn costs 0.30/kg and contains 9% protein and 2% fiber. "
    "Soybean meal costs 0.90/kg and contains 50% protein and 8% fiber. "
    "Final mix must contain at least 22% protein and at most 5% fiber. "
    "Minimize total cost."
)


def test_extract_first_json_object_from_markdown():
    text = "```json\\n{\\n  \\\"status\\\": \\\"ok\\\"\\n}\\n```" 

    parsed = extractor.extract_first_json_object(text)

    assert parsed == {"status": "ok"}


def test_normalize_general_blend_spec_percentages_and_names():
    spec = {
        "problem_type": "general_blend_cost_optimization",
        "product_mass_kg": "1,000",
        "objective": "minimize_cost",
        "sources": [
            {
                "name": "Corn",
                "cost_per_kg": "0.30",
                "qualities": {
                    "Protein": "9%",
                    "Fiber": "2%"
                }
            }
        ],
        "quality_lower_bounds": {
            "Protein": "22%"
        },
        "quality_upper_bounds": {
            "Fiber": "5%"
        }
    }

    normalized = extractor.normalize_general_blend_spec(spec)

    assert normalized["product_mass_kg"] == 1000
    assert normalized["sources"][0]["name"] == "corn"
    assert normalized["sources"][0]["qualities"]["protein"] == pytest.approx(0.09)
    assert normalized["sources"][0]["qualities"]["fiber"] == pytest.approx(0.02)
    assert normalized["quality_lower_bounds"]["protein"] == pytest.approx(0.22)
    assert normalized["quality_upper_bounds"]["fiber"] == pytest.approx(0.05)


def test_extract_general_blend_spec_with_mocked_llm(monkeypatch, tmp_path):
    llm_json = {
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
                "name": "soybean meal",
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

    def fake_call_llm_text(system_prompt, user_prompt):
        return json.dumps(llm_json)

    monkeypatch.setattr(extractor.llm_client, "call_llm_text", fake_call_llm_text)

    spec = extractor.extract_general_blend_spec(ANIMAL_FEED_PROMPT, trace_dir=tmp_path)

    assert spec["problem_type"] == "general_blend_cost_optimization"
    assert spec["product_mass_kg"] == 1000
    assert spec["sources"][1]["name"] == "soybean_meal"
    assert spec["quality_lower_bounds"]["protein"] == pytest.approx(0.22)
    assert spec["quality_upper_bounds"]["fiber"] == pytest.approx(0.05)
    assert (tmp_path / "llm_spec_extraction_trace.json").exists()


def test_validate_general_blend_spec_rejects_missing_quality_bound():
    spec = {
        "problem_type": "general_blend_cost_optimization",
        "product_mass_kg": 100,
        "objective": "minimize_cost",
        "sources": [
            {
                "name": "a",
                "cost_per_kg": 1,
                "qualities": {
                    "protein": 0.1
                }
            },
            {
                "name": "b",
                "cost_per_kg": 2,
                "qualities": {
                    "protein": 0.2
                }
            }
        ]
    }

    errors = extractor.validate_general_blend_spec(spec)

    assert any("quality lower or upper bound" in error for error in errors)
