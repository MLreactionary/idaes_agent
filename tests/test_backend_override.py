import json

import pytest

from app.codegen import CodegenError, write_generated_model


def test_write_generated_model_with_idaes_backend(tmp_path):
    spec = {
        "problem_type": "heater_energy_balance",
        "mode": "calculate_heat_duty",
        "temperature_in_k": 300.0,
        "temperature_out_k": 350.0,
        "mass_flow_kg_s": 1.0
    }

    model_path = write_generated_model(
        spec=spec,
        run_dir=tmp_path,
        backend_override="idaes"
    )

    generated_code = model_path.read_text(encoding="utf-8")
    structured_spec = json.loads(
        (tmp_path / "structured_spec.json").read_text(encoding="utf-8")
    )

    assert structured_spec["backend"] == "idaes"
    assert "from idaes.core import FlowsheetBlock" in generated_code
    assert '"backend": "idaes"' in generated_code


def test_backend_override_rejects_unavailable_backend(tmp_path):
    spec = {
        "problem_type": "splitter_mass_balance",
        "mode": "calculate_outlet_flows",
        "inlet_mass_flow_kg_s": 10.0,
        "outlet1_split_fraction": 0.3
    }

    with pytest.raises(CodegenError):
        write_generated_model(
            spec=spec,
            run_dir=tmp_path,
            backend_override="idaes"
        )
