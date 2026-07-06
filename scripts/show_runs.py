import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.store import list_runs


def main():
    rows = list_runs(limit=20)

    if not rows:
        print("No runs found.")
        return

    for row in rows:
        print("-" * 80)
        print(f"run_id:       {row['run_id']}")
        print(f"created_at:   {row['created_at']}")
        print(f"problem_type: {row['problem_type']}")
        print(f"mode:         {row['mode']}")
        print(f"status:       {row['status']}")
        print(f"verified:     {row['verified']}")
        print(f"num_failures: {row['num_failures']}")
        print(f"run_dir:      {row['run_dir']}")
        print(f"report_path:  {row['report_path']}")


if __name__ == "__main__":
    main()
