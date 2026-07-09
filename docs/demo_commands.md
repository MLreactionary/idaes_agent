# Demo Commands

## Full health check

```bash
python -m pytest -q
python scripts/run_benchmark.py --planner llm
python scripts/demo_all.py
```

Expected result:

```text
43 passed
benchmark: 15/15 passed
demo: 9/9 passed
```

## Repair demos

```bash
python scripts/run_repair_smoke.py
python scripts/run_splitter_repair_smoke.py
python scripts/run_utility_repair_smoke.py
```

## Streamlit UI

```bash
streamlit run scripts/ui_streamlit.py
```
