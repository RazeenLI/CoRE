# Experimental variants

Experiment-specific code stays under `experiments/`. Unchanged components are
imported from the standard implementation, while each controlled difference is
implemented locally.

## Registered pipeline variants

### `grain_profiler`

```text
Grain Profiler -> MPNet Candidate Selector -> Evolutor -> Validator -> Decision
```

The profile retains concise row-grain evidence and removes duplicated semantic
and value-pattern fields.

```bash
MODEL=grain_profiler DATASIZE=large ./run_cases.sh
```

### `constraint_filter`

```text
Profiler -> Candidate Selector -> Constraint Filter -> Evolutor -> Validator
```

Only the Evolutor's constraint context changes. Table-scoped constraints are
limited to selected tables, and foreign keys are retained only when both
endpoints are selected.

```bash
MODEL=constraint_filter DATASIZE=medium ./run_cases.sh
```

### `validator_prompt`

Uses a controlled Validator prompt variant while retaining the rest of the
standard pipeline.

```bash
MODEL=validator_prompt DATASIZE=large ./run_cases.sh
```

### `no_values`

Removes raw rows and literal sample values from LLM contexts while retaining
schema names, constraints, and non-literal profile statistics.

```bash
MODEL=no_values DATASIZE=large ./run_cases.sh
```

## Analysis-only experiments

- `embedding_evaluation`: candidate retrieval Hit@K and MRR without an LLM
  decision.
- `alternative_validity`: blinded annotation of reasonable operation choices.
- `continuous_evaluation`: ordered multi-step database evolution.
- `relation_scale`: controlled relation-count scalability.

See [the experiment guide](../docs/experiments.md) and each experiment's local
README. The former `selector` experiment is now the standard pipeline, and the
former `no_matcher` name is represented by the `no_selector` baseline.
