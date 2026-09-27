# Agents

The standard pipeline contains four agent roles.

## `profiler_agent.py`

Builds a semantic profile for the incoming table, including table meaning,
column meaning, aliases, types, and value-pattern evidence.

## `selector_agent.py`

Uses embedding retrieval to select a compact, high-recall set of existing
tables and candidate columns. It provides evidence to the Evolutor and does not
make the final operation decision.

## `evolutor_agent.py`

Chooses `insert_table`, `extend_table`, or `create_table` and produces column
placements and constraint signals used by the proposal builder.

## `validator_agent.py`

Reviews the proposal and its before/after database preview. It either accepts
the proposal or routes structured feedback to the agent responsible for a
revision.

All agents inherit shared calling and usage-accounting behavior from
`base_agent.py`. Pipeline routing and retry control live in
`model/core/orchestrator.py`, not in separate final-decision or memory agents.
