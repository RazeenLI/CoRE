# Relation-count scalability

This experiment keeps the incoming table and reference transition fixed while
adding unrelated Spider relations to the existing and expected RDB states.

Generate 30 operation-balanced cases for Chinook and Spider at four relation
counts (`original`, 25, 50, and 100):

```bash
python -m experiments.relation_scale.prepare_benchmark
```

Generated splits use the normal benchmark layout:

```text
data/Chinook/benchmarks/scale_original
data/Chinook/benchmarks/scale_25
data/Chinook/benchmarks/scale_50
data/Chinook/benchmarks/scale_100
data/Spider/benchmarks/scale_*
```

Run them with the existing runner, for example:

```bash
GPU_IDS=0 MODEL=standard DATASET=Chinook DATASIZE=scale_50 \
SKIP_COMPLETED=false ./run_cases.sh
```

Evaluate all generated splits after the runs finish:

```bash
python -m experiments.relation_scale.evaluate
```

The 25/50/100 settings are intentionally bounded to avoid the OOM risk of the
earlier 250/500/1000-relation plan.
