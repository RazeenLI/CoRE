# Top-k constraint filter experiment

Pipeline:

```text
Full Profiler -> MPNet Candidate Selector -> Constraint Filter
              -> Evolutor -> Validator -> Decision
```

This is a single-variable variant of Standard. Schema, profiles, sampled
values, selector evidence, prompts, agents, and routing are unchanged. Before
the Standard Evolutor is called, constraints are restricted to the subgraph
induced by the Selector's Top-k tables:

- primary keys, unique/check constraints, indexes, and inferred constraints
  retain only selected tables;
- a foreign key is retained only when both its source and referenced table are
  selected;
- no dangling constraint referring to a hidden table is included.

The full constraints remain in `TaskState` and are still used to apply the
final proposal. Filtering changes only the Evolutor input.

```bash
GPU_IDS=0,1,2,4 MODEL=constraint_filter DATASIZE=medium ./run_cases.sh
```
