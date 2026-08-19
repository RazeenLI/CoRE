# AIRDB Maintenance

AI-assisted relational database maintenance for integrating one incoming table into an existing relational database.

## 1. Available models

All models use the same case input, output layout, runner, and evaluation code.

| `MODEL` | Type | Pipeline |
|---|---|---|
| `standard` | Proposed method | Profiler → Qwen Matcher → Evolutor when needed → Validator → Decision |
| `oneshot` | LLM baseline | One-shot Evolutor → Decision |
| `magneto` | Retrieval + LLM baseline | MPNet retrieval → Qwen reranking → rule decision |
| `jl` | Rule baseline | Jaccard–Levenshtein matching → rule decision |
| `coma` | Rule baseline | COMA matching → rule decision |
| `no_matcher` | Ablation experiment | Profiler → One-shot-style Evolutor → Validator → Decision |
| `selector` | Selector experiment | Profiler → MPNet Candidate Selector → One-shot-style Evolutor → Validator → Decision |
| `selector_no_profiler` | Profiler ablation | MPNet Candidate Selector → One-shot-style Evolutor → Validator → Decision |

`selector_no_profiler` is an independent copy of `selector` with only the incoming Profiler stage removed. It retains the same Selector, Evolutor prompt, existing profiles, Validator, and Top-K settings.

## 2. Environment

```bash
cd /data1/runzel/AIRDB_maintenance
conda activate /data1/runzel/TimeSeriesImputation/.conda
python --version
```

The current environment uses Python 3.11 and the default agent configuration:

```text
configs/qwen3.5_9B.yaml
```

The Qwen configuration uses deterministic decoding (`do_sample=False`; temperature is represented by greedy decoding).

For a private or gated Hugging Face model, authenticate first:

```bash
hf auth login
hf auth whoami
```

### Additional dependencies

Magneto and Selector use `sentence-transformers/all-mpnet-base-v2`:

```bash
python -m pip install -r baselines/magneto/requirements.txt
```

JL and COMA use Valentine:

```bash
python -m pip install -r baselines/traditional/requirements.txt
```

The first Magneto or Selector run downloads MPNet from Hugging Face and caches it. JL and COMA do not load Qwen or an embedding model.

## 3. Input format

Each case must contain one existing RDB and exactly one incoming table:

```text
data/<dataset>/benchmarks/<size>/<case>/config.yaml
```

Example:

```yaml
existing_rdb:
  path: data/Chinook/benchmarks/large/case_0001/existing
  sample_num: 3
steps:
  - task_id: step_001
    path: data/Chinook/benchmarks/large/case_0001/incoming
    sample_num: 3
```

## 4. Run one case directly

General command:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,4 \
python -u main.py \
  --model <model> \
  --output save/Chinook/<model>/large/case_0001 \
  --agent-config configs/qwen3.5_9B.yaml \
  --data-config data/Chinook/benchmarks/large/case_0001/config.yaml
```

Replace `<model>` with one of:

```text
standard  oneshot  magneto  jl  coma  no_matcher  selector  selector_no_profiler
```

Example for No Matcher:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,4 \
python -u main.py \
  --model no_matcher \
  --output save/Chinook/no_matcher/large/case_0001 \
  --agent-config configs/qwen3.5_9B.yaml \
  --data-config data/Chinook/benchmarks/large/case_0001/config.yaml
```

Example for Selector:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,4 \
python -u main.py \
  --model selector \
  --output save/Chinook/selector/large/case_0001 \
  --agent-config configs/qwen3.5_9B.yaml \
  --data-config data/Chinook/benchmarks/large/case_0001/config.yaml
```

## 5. Batch runner

`run_cases.sh` discovers cases under:

```text
data/$DATASET/benchmarks/$DATASIZE/
```

and writes results to:

```text
save/$DATASET/$MODEL/$DATASIZE/
```

Run every case for one model and size:

```bash
GPU_IDS=0,1,2,4 MODEL=standard DATASET=Chinook DATASIZE=large \
./run_cases.sh
```

Run selected cases only:

```bash
GPU_IDS=0,1,2,4 MODEL=standard DATASIZE=large \
./run_cases.sh case_0001 case_0003 case_0010
```

### LLM models and experiments

```bash
GPU_IDS=0,1,2,4 MODEL=standard DATASIZE=large ./run_cases.sh
GPU_IDS=0,1,2,4 MODEL=oneshot DATASIZE=large ./run_cases.sh
GPU_IDS=0,1,2,4 MODEL=magneto DATASIZE=large ./run_cases.sh
GPU_IDS=0,1,2,4 MODEL=no_matcher DATASIZE=large ./run_cases.sh
GPU_IDS=0,1,2,4 MODEL=selector DATASIZE=large ./run_cases.sh
GPU_IDS=0,1,2,4 MODEL=selector_no_profiler DATASIZE=large ./run_cases.sh
```

### Rule baselines

JL and COMA do not require GPU inference. `GPU_IDS` may be omitted:

```bash
MODEL=jl DATASIZE=large ./run_cases.sh
MODEL=coma DATASIZE=large ./run_cases.sh
```

### Background execution

Use a distinct log for every model:

```bash
GPU_IDS=0,1,2,4 MODEL=no_matcher DATASIZE=large \
nohup ./run_cases.sh > logs/nohup_no_matcher_large.log 2>&1 &

GPU_IDS=0,1,2,4 MODEL=selector DATASIZE=large \
nohup ./run_cases.sh > logs/nohup_selector_large.log 2>&1 &

GPU_IDS=0,1,2,4 MODEL=selector_no_profiler DATASIZE=large \
nohup ./run_cases.sh > logs/nohup_selector_no_profiler_large.log 2>&1 &
```

Monitor progress:

```bash
tail -f logs/nohup_no_matcher_large.log
tail -f logs/nohup_selector_large.log
tail -f logs/nohup_selector_no_profiler_large.log
```

### Retry failed cases

Pass only the failed case names; completed cases do not need to run again:

```bash
GPU_IDS=0,1,2,4 MODEL=selector DATASIZE=large \
nohup ./run_cases.sh case_0029 case_0034 \
  > logs/nohup_selector_large_retry.log 2>&1 &
```

### Runner variables

| Variable | Default | Meaning |
|---|---|---|
| `MODEL` | `standard` | Any model listed in Section 1 |
| `DATASET` | `Chinook` | Dataset name |
| `DATASIZE` | `medium` | `small`, `medium`, or `large` |
| `GPU_IDS` | `0,1,3,4` | Value exported as `CUDA_VISIBLE_DEVICES` |
| `PYTHON_BIN` | `python` | Python executable |
| `MAX_ATTEMPTS` | `3` | Maximum attempts for a failed process |
| `RETRY_INTERVAL_SECONDS` | `60` | Delay between retry rounds |

## 6. Model-specific configuration

The shared configuration is in `configs/qwen3.5_9B.yaml`.

```yaml
magneto:
  embedding_model: sentence-transformers/all-mpnet-base-v2
  retrieval_top_k: 20

selector:
  embedding_model: sentence-transformers/all-mpnet-base-v2
  column_top_k: 20
  table_top_k: 5

traditional:
  column_match_confidence: 0.70
  insert_table_confidence: 0.70
  extend_table_confidence: 0.35
```

- Magneto retrieves Top-20 target columns and asks Qwen to return at most Top-10 reliable matches per incoming column.
- Selector retrieves Top-20 columns, ranks tables, and gives the Top-5 tables to the Evolutor. It does not make the final match or operation decision.
- JL/COMA thresholds must be tuned only on development data.

## 7. Output

All models use the same output layout:

```text
save/Chinook/<model>/<size>/<case>/
├── task_state.json
├── proposal.json
└── database/
    ├── schema.json
    ├── profiles.json
    ├── constraints.json
    └── tables/
        └── <table_name>.csv
```

- `task_state.json`: step results, routing, validation history, and trace.
- `proposal.json`: final structured integration proposal.
- `database/`: RDB after applying the proposal.
- `status: "succeeded"`: pipeline completed.
- `status: "failed"`: pipeline ran but ended in a workflow failure.

Python exceptions, model-loading failures, malformed LLM output, and CUDA OOM return a non-zero process code and are retried by `run_cases.sh`. Attempt logs are stored under `logs/<case>/`; each batch also produces `logs/batch_<timestamp>.log`.

## 8. Evaluation

Every model is evaluated from its `proposal.json` and generated `database/` with the same metrics:

```bash
python -m evaluation.evaluator
python -m evaluation.aggregate_result
```

Set the benchmark, result, and output paths in `evaluation/evaluator.py` before running. For example:

```python
evaluate_benchmark(
    benchmark_dir="data/Chinook/benchmarks/large",
    result_dir="save/Chinook/selector/large",
    output_csv_path="outputs/Chinook/selector/large.csv",
    sample_num=0,
)
```

See [Evaluation usage](evaluation/README.md) for case-level metrics and aggregation.

## 9. Main entry points

- `main.py`: model registry and CLI entry.
- `run_cases.sh`: batch discovery, execution, logging, and retries.
- `model/pipeline.py`: Standard pipeline.
- `baselines/oneshot/pipeline.py`: One-shot baseline.
- `baselines/magneto/pipeline.py`: Magneto baseline.
- `baselines/jl/pipeline.py`: JL baseline.
- `baselines/coma/pipeline.py`: COMA baseline.
- `experiments/no_matcher/pipeline.py`: No-Matcher experiment.
- `experiments/selector/pipeline.py`: Candidate-Selector experiment.
- `evaluation/evaluator.py`: case-level evaluation.
- `evaluation/aggregate_result.py`: aggregate metrics.

Additional details:

- [Magneto](baselines/magneto/README.md)
- [JL and COMA](baselines/traditional/README.md)
- [Experimental variants](experiments/README.md)
- [Evaluation](evaluation/README.md)
