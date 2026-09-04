from pathlib import Path

import yaml

from baselines.magneto.model.matcher import MagnetoMatcher
from baselines.magneto.model.orchestrator import Orchestrator
from model.core.llm_client import HFLLMClient
from model.utils.io import load_rdb, load_table, save_json, save_rdb, terminal_message


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def run_pipeline(
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    """Run one Magneto-style matching + rule-based integration task."""

    data_config = load_config(data_config_path)
    agent_config = load_config(agent_config_path)
    baseline_config = agent_config.get("magneto", {})

    existing_rdb = load_rdb(
        rdb_path=data_config["existing_rdb"]["path"],
        sample_num=data_config["existing_rdb"]["sample_num"],
    )
    llm_client = HFLLMClient(
        model_name=agent_config["LLMs"]["name"],
        default_mode=agent_config["LLMs"]["default_mode"],
        debug=False,
    )
    matcher = MagnetoMatcher(
        llm_client=llm_client,
        embedding_model_name=baseline_config.get(
            "embedding_model",
            "sentence-transformers/all-mpnet-base-v2",
        ),
        retrieval_top_k=baseline_config.get("retrieval_top_k", 20),
    )
    orchestrator = Orchestrator(
        matcher=matcher,
        save_path=save_root_path,
        config={**agent_config.get("orchestrator", {}), **baseline_config},
    )

    steps = data_config["steps"]
    if len(steps) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(steps)}.")
    step_config = steps[0]
    task_id = step_config.get("task_id", "task_01")
    incoming_table = load_table(
        table_path=step_config["path"],
        sample_num=step_config.get("sample_num", 0),
    )

    task_state, proposal = orchestrator.run_task(
        task_id=task_id,
        existing_rdb=existing_rdb,
        incoming_table=incoming_table,
    )
    task_state.llm_usage = llm_client.usage_summary()
    save_json(task_state.to_dict(), Path(save_root_path) / "task_state.json")
    save_json(proposal, Path(save_root_path) / "proposal.json")
    save_rdb(task_state.existing_rdb, save_root_path, folder_name="database")
    terminal_message("success", "Magneto baseline outputs were saved.")
