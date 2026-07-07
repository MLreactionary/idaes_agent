import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from scripts.run_problem import run_problem


def main():
    parser = argparse.ArgumentParser(description="IDAES Agent MVP CLI")

    parser.add_argument(
        "prompt",
        nargs="*",
        help="Natural-language process-modeling prompt."
    )

    parser.add_argument(
        "--planner",
        choices=["llm", "regex"],
        default="llm"
    )

    parser.add_argument(
        "--repair",
        action="store_true"
    )

    parser.add_argument(
        "--explain",
        action="store_true"
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Print demo commands."
    )

    args = parser.parse_args()

    if args.demo:
        print("Demo commands:")
        print()
        print('python scripts/idaes_cli.py "Heat water from 300 K to 350 K at 1 bar and report heat duty."')
        print('python scripts/idaes_cli.py "Water enters at 300 K and receives 100 kW of heat. What is the outlet temperature?"')
        print('python scripts/idaes_cli.py "I need to heat water from 25 C to 80 C using 100 kW. What mass flow rate can I process?"')
        print('python scripts/idaes_cli.py "Mix 1 kg/s of water at 300 K with 2 kg/s of water at 360 K. What is the outlet temperature?"')
        print('python scripts/idaes_cli.py "Split 10 kg/s of water with 30% going to outlet 1. What are the outlet flows?"')
        return

    if not args.prompt:
        raise SystemExit("Provide a prompt, or use --demo.")

    prompt = " ".join(args.prompt)

    result = run_problem(
        prompt=prompt,
        planner=args.planner,
        explain=args.explain,
        repair=args.repair,
        inject_bug=False,
        max_repair_attempts=1
    )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
