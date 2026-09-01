from pathlib import Path
from typing import Any

import yaml

from baselines.traditional.model.orchestrator import Orchestrator
from model.utils.io import load_rdb, load_table, save_json, save_rdb, terminal_message


def run_discovery_pipeline(
    *,
    method: str,
    matcher: Any,
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    with open(data_config_path, "r", encoding="utf-8") as file:
        data_config = yaml.safe_load(file)
    with open(agent_config_path, "r", encoding="utf-8") as file:
        agent_config = yaml.safe_load(file)
    config = {
        **agent_config.get("orchestrator", {}),
        **agent_config.get("discovery_rules", {}),
        **agent_config.get(method, {}),
    }
    existing_rdb = load_rdb(
        rdb_path=data_config["existing_rdb"]["path"],
        sample_num=data_config["existing_rdb"]["sample_num"],
    )
    steps = data_config["steps"]
    if len(steps) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(steps)}.")
    step = steps[0]
    incoming_table = load_table(
        table_path=step["path"],
        sample_num=step.get("sample_num", 0),
    )
    orchestrator = Orchestrator(
        matcher=matcher(config),
        matcher_name=method,
        save_path=save_root_path,
        config=config,
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
