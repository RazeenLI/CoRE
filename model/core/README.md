# Core runtime

The `core` package provides shared infrastructure for the standard pipeline.

## Modules

- `state.py`: task input snapshots, agent-result histories, routing, timing,
  and execution trace.
- `schemas.py`: typed result structures shared by agents and proposal code.
- `prompts.py`: LLM prompt templates.
- `llm_client.py`: Hugging Face model loading, chat-template rendering,
  generation, and token/time accounting.
- `embedding_retrieval.py`: SentenceTransformer loading and candidate-column
  retrieval.
- `orchestrator.py`: stage execution, validation retries, routing, and final
  update control.
- `decision.py`: automatic or interactive final decision handling.

Agents share LLM client instances so a model is loaded once per run. Agent
prompt construction, schema validation, and workflow routing remain outside
the low-level LLM client.
