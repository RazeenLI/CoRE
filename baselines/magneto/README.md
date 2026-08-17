# Magneto-Qwen baseline

This baseline retains Magneto's two model roles while using the same generative
LLM as the other project models:

1. `sentence-transformers/all-mpnet-base-v2` embeds serialized column headers,
   types, and sampled values and retrieves Top-k target columns for every
   incoming column.
2. Qwen3.5-9B reranks only those retrieved source-target column pairs.
3. Fixed rules aggregate matches by target table and select `insert_table`,
   `extend_table`, or `create_table`.
4. The shared rule-based proposal builder creates the final proposal.

No Standard-model profiles, Evolutor, or Validator are used. The MPNet
retriever is not fine-tuned on Chinook or the test labels.

Install the additional baseline dependency:

```bash
pip install -r baselines/magneto/requirements.txt
```

Run all Large cases:

```bash
GPU_IDS=0,1,2,5 MODEL=magneto DATASIZE=large ./run_cases.sh
```

The first run downloads MPNet from Hugging Face and caches it. Retriever and
rule settings are configured under `magneto` in the agent YAML.
