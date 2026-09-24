from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import torch

from model.agents.profiler_agent import ProfilerAgent
from model.agents.selector_agent import CandidateSelectorAgent
from model.core.llm_client import HFLLMClient
from model.core.orchestrator import Orchestrator
from model.core.state import TaskStatus
from model.pipeline import create_agents, load_config
from model.utils.io import load_rdb, load_table, save_json, save_rdb


ROOT = Path(__file__).resolve().parents[2]


def completed_step_output(step_output: Path) -> bool:
    """Return whether a saved step is safe to reuse in a rollout."""
    proposal_path = step_output / "proposal.json"
    state_path = step_output / "task_state.json"
    database_path = step_output / "database"
    schema_path = database_path / "schema.json"
    if not all(path.exists() for path in (proposal_path, state_path, schema_path)):
        return False

    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if state.get("status") != TaskStatus.SUCCEEDED:
        return False

    tables_dir = database_path / "tables"
    return all(
        (tables_dir / f"{table}.csv").exists()
        for table in schema.get("tables", {})
    )


def single_table_schema(schema: dict[str, Any], table: str) -> dict[str, Any]:
    return {
        "database": schema.get("database", "database"),
        "tables": {table: schema["tables"][table]},
    }


def refresh_empty_profiles(existing: dict[str, Any], profiler: ProfilerAgent) -> None:
    profile_tables = existing["profiles"].setdefault("tables", {})
    for table, table_schema in existing["schema"].get("tables", {}).items():
        table_profile = profile_tables.get(table, {})
        summary = table_profile.get("table", {}).get("summary")
        if summary:
            continue
        profile_tables[table] = profiler(
            incoming_schema=single_table_schema(existing["schema"], table),
            incoming_values=existing["sample_values"].get(table, []),
        )


def refresh_affected_profiles(
    existing: dict[str, Any],
    proposal: dict[str, Any],
    profiler: ProfilerAgent,
) -> None:
    profile_tables = existing["profiles"].setdefault("tables", {})
    for action in proposal.get("table_actions", []):
        table = action.get("table")
        if table not in existing["schema"].get("tables", {}):
            continue
        profile_tables[table] = profiler(
            incoming_schema=single_table_schema(existing["schema"], table),
            incoming_values=existing["sample_values"].get(table, []),
        )


def normalize_extend_values(
    updated: dict[str, Any],
    before: dict[str, Any],
    incoming: dict[str, Any],
    proposal: dict[str, Any],
) -> None:
    """Merge sampled Extend attributes into matching rows instead of appending."""
    if proposal.get("source_decision") != "extend_table":
        return
    for table_action in proposal.get("table_actions", []):
        if table_action.get("action") != "map":
            continue
        table = table_action.get("table")
        base_rows = copy.deepcopy(before["sample_values"].get(table, []))
        mapped_pairs = []
        all_pairs = []
        for column_action in table_action.get("column_actions", []):
            pairs = list(zip(
                column_action.get("source_columns", []),
                column_action.get("target_columns", []),
            ))
            all_pairs.extend(pairs)
            if column_action.get("action") == "map":
                mapped_pairs.extend(pairs)
        for incoming_row in incoming.get("sample_values", []):
            transformed = {
                target: incoming_row.get(source)
                for source, target in all_pairs
            }
            match = next((
                row for row in base_rows
                if mapped_pairs and all(
                    row.get(target) == incoming_row.get(source)
                    for source, target in mapped_pairs
                )
            ), None)
            if match is None:
                base_rows.append(transformed)
            else:
                match.update(transformed)
        updated["sample_values"][table] = base_rows


def create_runtime(agent_config: dict[str, Any]) -> tuple[Any, Any, CandidateSelectorAgent]:
    llm_client = HFLLMClient(
        model_name=agent_config["LLMs"]["name"],
        default_mode=agent_config["LLMs"]["default_mode"],
        reasoning_effort=agent_config["LLMs"].get("reasoning_effort"),
        trust_remote_code=agent_config["LLMs"].get("trust_remote_code", True),
        debug=False,
    )
    validator_client = llm_client
    validator_config = agent_config.get("validator_LLMs")
    if validator_config:
        minimum = int(validator_config.get("min_cuda_devices", 0))
        if minimum and torch.cuda.device_count() < minimum:
            raise RuntimeError(f"Validator requires {minimum} visible CUDA devices.")
        validator_client = HFLLMClient(
            model_name=validator_config["name"],
            default_mode=validator_config.get("default_mode", "non_thinking"),
            reasoning_effort=validator_config.get("reasoning_effort"),
            device_map=validator_config.get("device_map", "auto"),
            trust_remote_code=validator_config.get("trust_remote_code", True),
            debug=False,
        )
    agents = create_agents(llm_client, validator_client)
    selector_config = agent_config.get("standard", {})
    selector = CandidateSelectorAgent(
        embedding_model_name=selector_config.get(
            "embedding_model", "sentence-transformers/all-mpnet-base-v2"
        ),
        column_top_k=selector_config.get("column_top_k", 20),
        table_top_k=selector_config.get("table_top_k", 5),
    )
    return llm_client, agents, selector


def run_sequence(
    sequence_dir: Path,
    output_dir: Path,
    mode: str,
    agent_config: dict[str, Any],
    agents: dict[str, Any],
    selector: CandidateSelectorAgent,
    skip_completed: bool,
) -> None:
    metadata = json.loads((sequence_dir / "sequence.json").read_text(encoding="utf-8"))
    rollout_state = load_rdb(sequence_dir / "initial", sample_num=3)
    refresh_empty_profiles(rollout_state, agents["profiler"])
    reuse_completed = skip_completed

    for step in metadata["steps"]:
        index = int(step["step"])
        step_dir = sequence_dir / "steps" / f"step_{index:02d}"
        step_output = output_dir / f"step_{index:02d}"
        if reuse_completed and completed_step_output(step_output):
            if mode == "rollout":
                rollout_state = load_rdb(step_output / "database", sample_num=3)
            continue
        # Once a step must be rerun, every later rollout state in this sequence
        # depends on it and must be regenerated as well.
        reuse_completed = False
        existing = (
            load_rdb(step_dir / "oracle_existing", sample_num=3)
            if mode == "oracle" else rollout_state
        )
        refresh_empty_profiles(existing, agents["profiler"])
        incoming = load_table(step_dir / "incoming", sample_num=3)
        orchestrator = Orchestrator(
            profiler_agent=agents["profiler"],
            selector_agent=selector,
            evolutor_agent=agents["evolutor"],
            validator_agent=agents["validator"],
            save_path=step_output,
            config=agent_config["orchestrator"],
        )
        state, proposal = orchestrator.run_task(
            task_id=f"{sequence_dir.name}_step_{index:02d}",
            existing_rdb=existing,
            incoming_table=incoming,
        )
        updated = state.existing_rdb
        if state.status == TaskStatus.SUCCEEDED:
            normalize_extend_values(updated, existing, incoming, proposal)
            refresh_affected_profiles(updated, proposal, agents["profiler"])
        else:
            # A rejected/exhausted proposal is not applied. Preserve the
            # pre-step database so rollout continues from the last approved
            # state.
            updated = existing
        save_json(state.to_dict(), step_output / "task_state.json")
        save_json(proposal, step_output / "proposal.json")
        save_rdb(updated, step_output, folder_name="database")
        if mode == "rollout":
            rollout_state = updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("Spider", "TPCDS"), required=True)
    parser.add_argument("--mode", choices=("oracle", "rollout"), required=True)
    parser.add_argument("--agent-config", default="configs/qwen3.5_9B.yaml")
    parser.add_argument("--skip-completed", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    agent_config = load_config(args.agent_config)
    _, agents, selector = create_runtime(agent_config)
    source_root = ROOT / "data" / "continuous_benchmark" / args.dataset
    output_root = ROOT / "save" / "continuous" / args.dataset / args.mode
    for sequence_dir in sorted(source_root.glob("sequence_*")):
        print(f"running {args.mode}: {sequence_dir}", flush=True)
        run_sequence(
            sequence_dir=sequence_dir,
            output_dir=output_root / sequence_dir.name,
            mode=args.mode,
            agent_config=agent_config,
            agents=agents,
            selector=selector,
            skip_completed=args.skip_completed,
        )


if __name__ == "__main__":
    main()
