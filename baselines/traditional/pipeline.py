from pathlib import Path
from typing import Any

import yaml

from baselines.traditional.model.matcher import MatcherConfig, TraditionalMatcher
from baselines.traditional.model.orchestrator import Orchestrator
from model.utils.io import load_rdb, load_table, save_json, save_rdb, terminal_message


def load_config(config_path: str) -> dict[str, Any]:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def run_traditional_pipeline(
    *,
    method: str,
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    data_config = load_config(data_config_path)
    agent_config = load_config(agent_config_path)
    method_config = agent_config.get(method, {})
    common_config = agent_config.get("traditional", {})
    config = {**agent_config.get("orchestrator", {}), **common_config, **method_config}

    existing_rdb = load_rdb(
        rdb_path=data_config["existing_rdb"]["path"],
        sample_num=data_config["existing_rdb"]["sample_num"],
    )
    matcher = TraditionalMatcher(
        method=method,
        config=MatcherConfig(
            assignment_threshold=config.get("assignment_threshold", 0.70),
            levenshtein_threshold=config.get("levenshtein_threshold", 0.80),
            coma_use_schema=config.get("use_schema", True),
            coma_use_instances=config.get("use_instances", True),
            coma_delta=config.get("delta", 0.15),
        ),
    )
    orchestrator = Orchestrator(
        matcher=matcher,
        matcher_name=method,
        save_path=save_root_path,
        config=config,
    )

    steps = data_config["steps"]
    if len(steps) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(steps)}.")
    step = steps[0]
    incoming_table = load_table(
        table_path=step["path"],
        sample_num=step.get("sample_num", 0),
    )
    state, proposal = orchestrator.run_task(
        task_id=step.get("task_id", "task_01"),
        existing_rdb=existing_rdb,
        incoming_table=incoming_table,
    )
    save_json(state.to_dict(), Path(save_root_path) / "task_state.json")
    save_json(proposal, Path(save_root_path) / "proposal.json")
    save_rdb(state.existing_rdb, save_root_path, folder_name="database")
    terminal_message("success", f"{method.upper()} baseline outputs were saved.")
