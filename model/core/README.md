# `core/`：公共基础设施

The `core/` directory contains shared infrastructure used by all agents.

## `state.py`

Defines the shared pipeline state.

Each agent reads from and writes to this state.

> 保存一次运行的 shared state。
> 
> 所有 agent 都读写这个对象。
>
> 这是整个 pipeline 的“工作区”。

Example fields:

```
incoming_table
target_context
source_profile
matching_result
evolution_proposal
validation_report
final_decision
```

## `schemas.py`

Defines structured data models for the system outputs.

> 定义所有标准 JSON 输出格式。

Typical schemas include:

```
SourceProfile
ColumnProfile
MatchingResult
ColumnMapping
EvolutionProposal
ValidationReport
FinalDecision
```

This file helps keep agent outputs consistent and machine-readable.

## `prompts.py`

Stores all LLM prompt templates.

> 放所有 LLM prompt 模板。

Examples:

```
PROFILER_PROMPT
MATCHER_PROMPT
EVOLUTION_PROMPT
VALIDATOR_PROMPT
```

Keeping prompts in one place makes prompt tuning easier.

## `llm_client.py`

Provides a unified interface for calling local or remote LLMs.

> 所有 agent 都通过它调用 LLM：

Examples of possible models:

```
Qwen3-8B
Llama-3.1-8B-Instruct
```

All agents call the LLM through this wrapper instead of directly calling model APIs.

## `embedding_client.py`

Provides a unified interface for generating embeddings.

> 统一生成 embedding。

Possible embedding models include:

```
bge-m3
Qwen3-Embedding-0.6B
all-MiniLM-L6-v2
```

Embeddings are used for table and column retrieval.

## `orchestrator.py`

Controls the full pipeline.

> 控制整个流程。
>
> 这是 pipeline 的主控制器。

Responsibilities:

```
call the Profiler Agent
call the Matcher Agent
route high-confidence matches to final decision
route partial or low-confidence matches to the Evolution Agent
call the Validator Agent
route failed validations back to the correct agent
generate the final decision
update memory and metadata
```