# Experimental model variants

Experiment-specific code stays under `experiments/`; no experiment imports
another experiment or baseline. Components that are intentionally unchanged
are imported from the frozen Standard implementation, while each experimental
difference is implemented locally.

## `grain_profiler`

```text
Grain Profiler -> MPNet Candidate Selector -> Evolutor -> Validator -> Decision
```

The workflow matches Standard. Only the profile representation changes:
incoming and existing profiles retain concise row-grain evidence and remove
duplicated descriptions, aliases, schema fields, and value-pattern fields.

```bash
MODEL=grain_profiler DATASIZE=large ./run_cases.sh
```

## `embedding_evaluation`

This is a retrieval-only experiment rather than a pipeline model. It compares
SentenceTransformer encoders using target-table and exact-column Hit@K/MRR and
does not call Qwen. See `embedding_evaluation/README.md` for the command.

## `no_sample_values` (planned privacy experiment)

This experiment evaluates deployments in which database and incoming-table
cell values cannot be disclosed to the LLM. It follows the Standard pipeline
but removes all example rows and literal sample values from the incoming-table
and existing-RDB contexts. Schema names, constraints, and non-literal aggregate
profile statistics remain available; profile fields containing raw values must
also be removed.

Compare this variant with Standard using decision, proposal, constraint, and
validity metrics, together with prompt tokens and elapsed time. The comparison
measures how much the framework depends on value-level evidence and whether it
remains usable under this privacy restriction.

## `constraint_filter`

```text
Full Profiler -> MPNet Candidate Selector -> Constraint Filter
              -> Evolutor -> Validator -> Decision
```

This is a single-variable Standard variant. Only the Evolutor's constraint
context changes: table-scoped constraints retain Top-k tables, and foreign keys
are retained only when both endpoints are in Top-k. The full TaskState and
proposal application remain unchanged.

```bash
MODEL=constraint_filter DATASIZE=medium ./run_cases.sh
```

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
