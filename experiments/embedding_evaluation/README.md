# Embedding retrieval evaluation

This folder is exploratory and is intentionally separate from `evaluation/`.
It evaluates the selector's embedding retrieval before any LLM decision.

Metrics:

- table Hit@K and MRR for cases whose expected target already exists;
- exact column Hit@K and MRR for mappings to existing columns;
- total and mean retrieval time;
- per-case ranks and Top-5 evidence for error analysis.

New columns and new tables are excluded because retrieval cannot return schema
elements that do not yet exist. The denominator for every metric is saved in
the JSON report.

Evaluate the current MPNet encoder:

```bash
python -m experiments.embedding_evaluation.evaluate \
  --cases-root data/TPCDS/benchmarks/large \
  --models sentence-transformers/all-mpnet-base-v2 \
  --k 1 3 5 10 20 \
  --output save/embedding_evaluation/TPCDS/large.json
```

Compare multiple SentenceTransformer models by passing all model names after
`--models`. Models are loaded and evaluated sequentially to limit GPU memory.
No Qwen call is made.

Curated reports under `save/embedding_evaluation/` are versioned as research
artifacts. Other files under `save/` remain local runtime outputs.
