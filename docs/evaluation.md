# Evaluation

Evaluation has two stages:

1. `evaluation.evaluator` computes per-case metrics and writes CSV files.
2. `evaluation.aggregate_result` aggregates one or more CSV files.

## Case-level evaluation

Select datasets, models, and sizes by editing the configuration constants near
the top of `evaluation/evaluator.py`:

```python
DATASETS = ["Chinook", "MONDIAL", "TPCDS"]
MODELS = ["standard", "oneshot"]
SIZES = ["small", "medium", "large"]
```

The evaluator uses these paths:

```text
benchmark: data/<dataset>/benchmarks/<size>
results:   save/<dataset>/<model>/<size>
CSV:       outputs/<dataset>/<model>/<size>.csv
```

Run it from the repository root:

```bash
python -m evaluation.evaluator
```

Missing proposals or database outputs are recorded as missing results rather
than silently dropped. Successful cases include decision, placement, proposal,
constraint, validity, preservation, tuple, complexity, timing, and LLM-usage
metrics.

## Aggregation

Set `RESULT_FILES` near the top of `evaluation/aggregate_result.py`:

```python
RESULT_FILES = [
    "outputs/Chinook/standard/small.csv",
    "outputs/Chinook/standard/medium.csv",
    "outputs/Chinook/standard/large.csv",
]
```

Then run:

```bash
python -m evaluation.aggregate_result
```

Summaries are written under `outputs/summary/`. Repeated runs can be named
`medium_1.csv`, `medium_2.csv`, and so on; the aggregator uses the suffix as a
run identifier and reports mean and standard deviation where applicable.

## Retrieval-only evaluation

The embedding experiment evaluates candidate retrieval before LLM decision
making:

```bash
python -m experiments.embedding_evaluation.evaluate \
  --cases-root data/TPCDS/benchmarks/large \
  --models sentence-transformers/all-mpnet-base-v2 \
  --k 1 3 5 10 20 \
  --output save/embedding_evaluation/TPCDS/large.json
```

Curated JSON reports in `save/embedding_evaluation/` are committed as artifact
evidence. Other runtime outputs under `save/` remain ignored.
