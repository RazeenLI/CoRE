# Minimal continuous evaluation

The benchmark contains ten 10-step sequences: five from Spider databases and
five independently sampled from TPC-DS. Each sequence contains four Extend,
three Create, and three Insert transitions.

Generate the structural benchmark:

```bash
python -m experiments.continuous_evaluation.prepare_sequences
```

Run Oracle-state and Rollout without an additional shell script:

```bash
CUDA_VISIBLE_DEVICES=0 nohup python -m experiments.continuous_evaluation.run_sequences \
  --dataset Spider --mode oracle --agent-config configs/qwen3.5_9B.yaml \
  > logs/continuous_spider_oracle.log 2>&1 &

CUDA_VISIBLE_DEVICES=1 nohup python -m experiments.continuous_evaluation.run_sequences \
  --dataset Spider --mode rollout --agent-config configs/qwen3.5_9B.yaml \
  > logs/continuous_spider_rollout.log 2>&1 &
```

Replace `Spider` with `TPCDS` for the other five sequences. Oracle-state loads
the gold state before every step. Rollout carries the RDB produced by the
preceding prediction into the next step. The runner keeps the models loaded
across the entire batch and supports `--skip-completed`.

Evaluate per-step decision/proposal quality and final schema exact match:

```bash
python -m experiments.continuous_evaluation.evaluate \
  --dataset Spider --mode rollout
```
