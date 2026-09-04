from pathlib import Path

import yaml

from baselines.magneto.model.matcher import MagnetoMatcher
from baselines.magneto_llm.orchestrator import Orchestrator
from model.agents.evolutor_agent import EvolutorAgent
from model.core.llm_client import HFLLMClient
from model.utils.io import load_rdb, load_table, save_json, save_rdb, terminal_message


def run_pipeline(data_config_path: str, agent_config_path: str,
                 save_root_path: str) -> None:
    with open(data_config_path, "r", encoding="utf-8") as file:
        data_config = yaml.safe_load(file)
    with open(agent_config_path, "r", encoding="utf-8") as file:
        agent_config = yaml.safe_load(file)

    existing_rdb = load_rdb(
        rdb_path=data_config["existing_rdb"]["path"],
        sample_num=data_config["existing_rdb"]["sample_num"],
    )
    client = HFLLMClient(
        model_name=agent_config["LLMs"]["name"],
        default_mode=agent_config["LLMs"]["default_mode"],
        debug=False,
    )
    config = agent_config.get("magneto", {})
    matcher = MagnetoMatcher(
        llm_client=client,
        embedding_model_name=config.get(
            "embedding_model", "sentence-transformers/all-mpnet-base-v2"),
        retrieval_top_k=config.get("retrieval_top_k", 20),
    )
    orchestrator = Orchestrator(
        matcher=matcher,
        evolutor=EvolutorAgent(client),
        save_path=save_root_path,
        config=agent_config.get("orchestrator", {}),
    )
    steps = data_config["steps"]
    if len(steps) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(steps)}.")
    step = steps[0]
    incoming = load_table(step["path"], sample_num=step.get("sample_num", 0))
    state, proposal = orchestrator.run_task(
        task_id=step.get("task_id", "task_01"),
        existing_rdb=existing_rdb,
        incoming_table=incoming,
    )
    state.llm_usage = client.usage_summary()
    save_json(state.to_dict(), Path(save_root_path) / "task_state.json")
    save_json(proposal, Path(save_root_path) / "proposal.json")
    save_rdb(state.existing_rdb, save_root_path, folder_name="database")
    terminal_message("success", "Magneto-LLM baseline outputs were saved.")
