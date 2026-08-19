# Experimental model variants

These variants are isolated from `model/` so the current Standard remains
reproducible. They are also isolated from each other: each experiment owns its
pipeline, orchestrator, Evolutor, and prompt, and there is no shared experiment
implementation whose modification could change both results.

## `no_matcher`

```text
Profiler -> Evolutor (relationship + operation) -> Validator -> Decision
```

The Evolutor receives all existing tables. Validator revisions always return
to the Evolutor, including an `insert_table` revision that the shared Standard
validator labels as `matcher`.

```bash
MODEL=no_matcher DATASIZE=large ./run_cases.sh
```

## `selector`

```text
Profiler -> MPNet Candidate Selector -> Evolutor -> Validator -> Decision
```

The selector uses `all-mpnet-base-v2` and makes no LLM call. It keeps a
high-recall set of tables and one best retrieved column per source-column and
candidate-table pair. The Evolutor makes the final relationship and operation
decision; selector scores are evidence, not decisions. The full selector result
is retained in `task_state.json`, while the Evolutor prompt receives only
`selected_tables` and compact `column_candidates` to avoid duplicate context.

Configuration defaults:

```yaml
selector:
  embedding_model: sentence-transformers/all-mpnet-base-v2
  column_top_k: 15
  table_top_k: 5
```

```bash
MODEL=selector DATASIZE=large ./run_cases.sh
```

Write each variant to its own `save/Chinook/<model>/<size>` directory and do
not overwrite Standard while comparing accuracy, validity, and elapsed time.
