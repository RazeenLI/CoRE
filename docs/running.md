# Running CoRE

## Case format

Each run consumes one YAML file describing an existing RDB and one or more
ordered incoming-table steps. Benchmark cases in this repository contain one
incoming table:

```yaml
existing_rdb:
  path: data/Chinook/benchmarks/large/case_0001/existing
  sample_num: 3
steps:
  - task_id: step_001
    path: data/Chinook/benchmarks/large/case_0001/incoming
    sample_num: 3
```

## Run one case

```bash
python -u main.py \
  --model standard \
  --output save/Chinook/standard/large/case_0001 \
  --agent-config configs/qwen3.5_9B.yaml \
  --data-config data/Chinook/benchmarks/large/case_0001/config.yaml
```

Use `python main.py --help` to see the registered model names and required
arguments.

## Batch runner

`run_cases.sh` discovers cases under
`data/$DATASET/benchmarks/$DATASIZE/` and writes outputs under
`save/$DATASET/$OUTPUT_MODEL/$DATASIZE/`.

Run a complete split:

```bash
GPU_IDS=0 MODEL=standard DATASET=Chinook DATASIZE=large ./run_cases.sh
```

Run selected cases:

```bash
GPU_IDS=0 MODEL=standard DATASET=Chinook DATASIZE=large \
  ./run_cases.sh case_0001 case_0003 case_0010
```

Rule baselines do not require an LLM:

```bash
MODEL=jl DATASET=Chinook DATASIZE=large ./run_cases.sh
MODEL=coma DATASET=Chinook DATASIZE=large ./run_cases.sh
```

### Runner variables

| Variable | Default | Meaning |
|---|---|---|
| `MODEL` | `standard` | Registered pipeline name |
| `OUTPUT_MODEL` | value of `MODEL` | Output directory label |
| `DATASET` | `Chinook` | Dataset directory name |
| `DATASIZE` | `medium` | Benchmark split |
| `GPU_IDS` | `0,1,3,4` | Exported as `CUDA_VISIBLE_DEVICES` |
| `PYTHON_BIN` | `python` | Python executable |
| `AGENT_CONFIG` | `configs/qwen3.5_9B.yaml` | Agent configuration |
| `MAX_ATTEMPTS` | `3` | Attempts for a failed process |
| `RETRY_INTERVAL_SECONDS` | `60` | Wait between retry rounds |

Use machine-appropriate GPU identifiers rather than relying on the default.

## Background runs

Write each batch to a distinct log:

```bash
GPU_IDS=0 MODEL=standard DATASET=Chinook DATASIZE=large \
  nohup ./run_cases.sh > logs/nohup_standard_large.log 2>&1 &
```

Monitor it with:

```bash
tail -f logs/nohup_standard_large.log
```

## Output layout

```text
save/<dataset>/<model>/<size>/<case>/
├── task_state.json
├── proposal.json
└── database/
    ├── schema.json
    ├── profiles.json
    ├── constraints.json
    └── tables/
        └── <table_name>.csv
```

- `task_state.json` records stage results, routing, validation history, timing,
  and LLM usage.
- `proposal.json` is the final structured integration proposal.
- `database/` contains the database state after applying the proposal.

Runtime outputs, logs, and ordinary evaluation outputs are ignored by Git.
Curated retrieval reports under `save/embedding_evaluation/` are retained as
reproducibility artifacts.
