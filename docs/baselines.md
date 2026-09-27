# Baselines and ablations

All registered pipelines consume the same case format and write the same core
output layout. `main.py` is the authoritative model registry.

## LLM baselines

- `llm_matcher`: LLM-based matching followed by evolution when needed.
- `oneshot`: direct proposal generation in one LLM stage.

## Matching and discovery baselines

- `magneto`: MPNet retrieval, Qwen reranking, and deterministic proposal rules.
- `santos`: case-local synthesized knowledge-base matching.
- `embdi`: case-local graph construction and Skip-gram training.
- `starmie`: external Starmie encoder checkpoint with AIRDB proposal rules.
- `jl`: Jaccard-Levenshtein matching through Valentine.
- `coma`: hybrid COMA matching through Valentine.

These systems are adaptations because the upstream projects do not directly
emit CoRE's database-maintenance proposal format. Their correspondence evidence
is converted through a shared adapter where applicable.

## LLM adapter variants

- `magneto_llm`
- `coma_llm`
- `starmie_llm`

These variants pass baseline evidence to the Evolutor to separate matching
quality from errors introduced by deterministic proposal conversion.

## Ablations

- `no_profiler`
- `no_selector`
- `no_validator`

Implementation-specific notes and upstream attribution are kept in the
README files under `baselines/`. Starmie source code and checkpoints are not
vendored; follow `baselines/starmie/README.md` to prepare them externally.
