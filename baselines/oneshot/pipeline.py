from pathlib import Path

import yaml

from baselines.oneshot.model.agent import EvolutorAgent
from baselines.oneshot.model.orchestrator import Orchestrator
from model.core.llm_client import HFLLMClient
from model.utils.io import (
    load_rdb,
    load_table,
    save_json,
    save_rdb,
    terminal_message,
)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def create_agents(llm_client: HFLLMClient) -> dict[str, EvolutorAgent]:
    return {
        "evolutor": EvolutorAgent(llm_client),
    }


def run_pipeline(
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    """Run one one-shot RDB integration task."""

    data_config = load_config(data_config_path)
    agent_config = load_config(agent_config_path)

    existing_rdb = load_rdb(
        rdb_path=data_config["existing_rdb"]["path"],
        sample_num=data_config["existing_rdb"]["sample_num"],
    )
    terminal_message("success", f"Load existing relational database with keys: {existing_rdb.keys()}.")

    llm_client = HFLLMClient(
        model_name=agent_config["LLMs"]["name"],
        default_mode=agent_config["LLMs"]["default_mode"],
        debug=False,
    )
    agents = create_agents(llm_client)
    terminal_message("success", "LLM Client and Agents are created.")

    orchestrator = Orchestrator(
        evolutor_agent=agents["evolutor"],
        save_path=save_root_path,
        config=agent_config["orchestrator"],
    )
    terminal_message("success", "One-shot Orchestrator is created.")

    steps = data_config["steps"]
    if len(steps) != 1:
        raise ValueError(
            f"Exactly one incoming table is required, got {len(steps)}."
        )

    step_config = steps[0]
    task_id = step_config.get("task_id", "task_01")
    incoming_table = load_table(
        table_path=step_config["path"],
        sample_num=step_config.get("sample_num", 0),
    )
    terminal_message("success", f"Task {task_id} load incoming table with keys: {incoming_table.keys()}.")

    task_state, proposal = orchestrator.run_task(
        task_id=task_id,
        existing_rdb=existing_rdb,
        incoming_table=incoming_table,
    )
    existing_rdb = task_state.existing_rdb
    terminal_message("success", f"Task {task_id} running finished.")

    task_state_path = Path(save_root_path) / "task_state.json"
    save_json(task_state.to_dict(), task_state_path)
    terminal_message("success", f"Task state is saved at {task_state_path}.")

    proposal_path = Path(save_root_path) / "proposal.json"
    save_json(proposal, proposal_path)
    terminal_message("success", f"Proposal is saved at {proposal_path}.")

    database_path = save_rdb(
        existing_rdb,
        save_root_path,
        folder_name="database",
    )
    terminal_message("success", f"Relational database is saved at {database_path}.")
