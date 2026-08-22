# Grain-focused profiler experiment

Pipeline:

```text
Grain Profiler -> MPNet Candidate Selector -> Evolutor -> Validator -> Decision
```

This experiment changes only the profile representation. Incoming and existing
profiles use the same compact fields:

```text
table:   entity, role, row_grain
column:  semantic_type, business_concept, grain_role
```

Verbose summaries, meanings, aliases, dtypes, value patterns, names, and sample
values are not repeated inside the profile. Schema and sampled values remain in
their normal Evolutor context.

Existing profiles are compressed deterministically instead of re-running Qwen
once per existing table. This keeps the LLM call count equal to Standard.

```bash
GPU_IDS=0,1,2,4 MODEL=grain_profiler DATASIZE=large ./run_cases.sh
```
