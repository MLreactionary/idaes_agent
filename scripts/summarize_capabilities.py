import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


CAPABILITY_MAP = [
    ("heater/cooler sensible heat duty", ["heat_kelvin_default_flow", "heat_celsius_default_flow", "cool_celsius_with_flow", "heat_kelvin_with_flow", "heat_rich_units_kg_hr_kj_cp"]),
    ("heater outlet temperature", ["outlet_temperature_from_heat_duty", "outlet_temperature_with_heat_removed"]),
    ("heater mass flow calculation", ["mass_flow_from_heat_duty_and_temperature_rise"]),
    ("adiabatic two-stream mixer", ["adiabatic_mixer_two_water_streams", "adiabatic_mixer_rich_units_celsius_kg_hr"]),
    ("unsupported problem rejection", ["unsupported_flash", "unsupported_reactor"]),
    ("two-source blend cost optimization", ["blend_cost_optimization_two_sources"]),
    ("general blend optimization", ["general_blend_cost_optimization_three_sources"]),
    ("general blend source availability bounds", ["general_blend_cost_optimization_with_source_bounds"]),
    ("general blend minimum required usage", ["general_blend_cost_optimization_with_min_required_source"]),
    ("general blend infeasibility diagnosis", ["general_blend_infeasible_max_availability", "general_blend_infeasible_min_exceeds_max", "general_blend_infeasible_total_min_required", "general_blend_infeasible_quality_limit"]),
    ("utility emissions-constrained optimization", ["utility_emissions_optimization"]),
    ("utility cost-emissions sweep", ["utility_emissions_cap_sweep"]),
    ("multi-period utility planning", ["utility_multi_period_emissions_cap"]),
    ("IDAES heater backend parity", ["idaes_heat_duty_backend", "idaes_outlet_temperature_backend", "idaes_mass_flow_backend"]),
]


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def summarize(benchmark_path):
    benchmark = load_json(benchmark_path)
    by_id = {case["id"]: case for case in benchmark["case_results"]}

    lines = []
    lines.append("# Capability Evaluation Summary")
    lines.append("")
    lines.append(f"- Benchmark ID: `{benchmark.get('benchmark_id')}`")
    lines.append(f"- Planner: `{benchmark.get('planner')}`")
    lines.append(f"- Total cases: `{benchmark.get('total_cases')}`")
    lines.append(f"- Passed cases: `{benchmark.get('passed_cases')}`")
    lines.append(f"- Failed cases: `{benchmark.get('failed_cases')}`")
    lines.append("")

    lines.append("## Capability Matrix")
    lines.append("")
    lines.append("| Capability | Cases | Status |")
    lines.append("|---|---:|---|")

    for capability, case_ids in CAPABILITY_MAP:
        present = [case_id for case_id in case_ids if case_id in by_id]
        passed = [case_id for case_id in present if by_id[case_id].get("passed")]
        status = "PASS" if len(present) == len(case_ids) and len(passed) == len(case_ids) else "GAP"
        lines.append(f"| {capability} | `{len(passed)}/{len(case_ids)}` | {status} |")

    lines.append("")
    lines.append("## Supported Scope")
    lines.append("")
    lines.append("- Deterministic algebraic heater/cooler calculations with heat duty, outlet temperature, and mass flow modes.")
    lines.append("- Pyomo optimization scaffolds for blend and utility planning problems.")
    lines.append("- General blend optimization with multiple sources, quality limits, max availability bounds, and minimum usage requirements.")
    lines.append("- Structured infeasibility diagnosis for common general blend failures.")
    lines.append("- Utility planning with emissions caps, cost-emissions sweep evaluation, and multi-period aggregate emissions constraints.")
    lines.append("- Registry-backed model selection trace for supported model families.")
    lines.append("- IDAES-backed heater scaffold parity for the current heater modes.")
    lines.append("")

    lines.append("## Explicit Non-Scope")
    lines.append("")
    lines.append("- Flash calculations are intentionally rejected in this benchmark.")
    lines.append("- Reactor kinetics are intentionally rejected in this benchmark.")
    lines.append("- The IDAES heater backend is currently a FlowsheetBlock-backed sensible-heat scaffold, not a full property-package unit model.")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-json", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark_json)
    output_path = Path(args.output) if args.output else benchmark_path.with_name(benchmark_path.stem + "_capabilities.md")

    output_path.write_text(summarize(benchmark_path), encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
