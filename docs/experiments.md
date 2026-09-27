# Experiments

Controlled variants live under `experiments/` and reuse unchanged components
from the standard pipeline.

## Pipeline variants

- `grain_profiler`: retains concise row-grain evidence and removes duplicated
  profile fields.
- `constraint_filter`: restricts the Evolutor's constraint context to the
  selected table subgraph.
- `validator_prompt`: evaluates a Validator prompt variant.
- `no_values`: removes literal sample values from LLM inputs while retaining
  schema names, constraints, and non-literal profile statistics.

## Analysis experiments

- `embedding_evaluation`: retrieval-only Hit@K and MRR evaluation.
- `alternative_validity`: blinded human annotation of operation-level
  alternatives.
- `continuous_evaluation`: evaluation over ordered table sequences.
- `relation_scale`: controlled relation-count scalability analysis.

Each experiment has a local README with its command and design constraints.
Generated runtime results belong under `save/`; only curated artifact outputs
are versioned.

## Current result notes

Model-sensitivity and matching-adapter runs may contain missing cases. Coverage
must always be reported, and strictly paired comparisons must use the common
successful-case subset or explicitly count failures. Do not compute quality
metrics only over a silently selected successful subset.

Paper tables and final experiment status will be updated alongside the paper
release.
