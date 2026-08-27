# Validator Prompt Experiment

This experiment reuses the complete Standard pipeline and changes only the
Validator prompt. The prompt explicitly checks decision-operation consistency,
column coverage, constraint validity, preservation, and preview scope.

Run a complete benchmark size with:

```bash
GPU_IDS=0,1 MODEL=validator_prompt DATASET=MONDIAL DATASIZE=small ./run_cases.sh
```

Outputs are written under `save/<dataset>/validator_prompt/<size>/`.
