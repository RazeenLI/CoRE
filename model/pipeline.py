# run_pipeline.py
import torch
import argparse
from pathlib import Path

import pandas as pd
import yaml

from model.utils.io import load_rdb, save_rdb, load_table, terminal_message

# from core.orchestrator import Orchestrator
# from core.task import IngestionTask
# from core.io import , save_run_state

from model.core.llm_client import HFLLMClient
from model.core.orchestrator import Orchestrator

from model.agents.base_agent import BaseAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.matcher_agent import MatcherAgent
from model.agents.evolutor_agent import EvolutorAgent
from model.agents.validator_agent import ValidatorAgent

# from agents.decision import DecisionAgent


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# def load_incoming_task(step_config: dict) -> IngestionTask:
#     """
#     Load one incoming table and convert it into an IngestionTask.
#     """

#     task_id = step_config["task_id"]
#     table_name = step_config["table_name"]
#     table_path = step_config["table_path"]

#     incoming_table = pd.read_csv(table_path)

#     schema = None
#     if "schema_path" in step_config and step_config["schema_path"]:
#         with open(step_config["schema_path"], "r", encoding="utf-8") as f:
#             schema = yaml.safe_load(f)

#     return IngestionTask(
#         task_id=task_id,
#         table_name=table_name,
#         table=incoming_table,
#         schema=schema,
#         source_path=table_path,
#     )


def create_agents(llm_client):
    """
    Create all agents used by the orchestrator.

    For now, agents can be simple classes.
    Later, you can pass llm_client, embedding_model, prompts, etc.
    """
    profiler_agent = ProfilerAgent(llm_client)
    matcher_agent = MatcherAgent(llm_client)
    evolutor_agent = EvolutorAgent(llm_client)
    validator_agent = ValidatorAgent(llm_client)
    decision_agent = BaseAgent(llm_client)

    return {
        "profiler": profiler_agent,
        "matcher": matcher_agent,
        "evolutor": evolutor_agent,
        "validator": validator_agent,
        "decision": decision_agent,
    }


def run_pipeline(
    data_config_path: str = "data/Chinook/benchmarks/small_case_A_remove_columns/config.yaml",
    agent_config_path: str = "data/Chinook/benchmarks/small_case_A_remove_columns/existing",
    save_root_path: str="save"
) -> None:
    """
    Run the full RDB integration pipeline.
    1. load exsting edb 
    2. create Agents 
    3. create Orchestrator 
    4. loop: add tasks and incoming table 
    5. finish loop finish all
    """

    # 0. Load config file 
    data_config = load_config(data_config_path)
    agent_config = load_config(agent_config_path)

    # 1. Load existing RDB
    existing_rdb = load_rdb(
        rdb_path=data_config["existing_rdb"]["path"], 
        sample_num=data_config["existing_rdb"]["sample_num"],
    )

    terminal_message("success", f"Load existing relational database with keys: {existing_rdb.keys()}.")

    # 2. Create LLM Client
    llm_client = HFLLMClient(
        model_name=agent_config["LLMs"]["name"],
        default_mode=agent_config["LLMs"]["default_mode"],
        debug=False,
    )

    # print("CUDA available:", torch.cuda.is_available())
    # print("Device map:", getattr(llm_client.model, "hf_device_map", None))
    
    # 3. Create agents
    agents = create_agents(llm_client)

    terminal_message("success", f"LLM Client and Agents are created.")

    # 3. Create orchestrator
    orchestrator = Orchestrator(
        profiler_agent=agents["profiler"],
        matcher_agent=agents["matcher"],
        evolutor_agent=agents["evolutor"],
        validator_agent=agents["validator"],
        decision_agent=agents["decision"],
        existing_rdb=existing_rdb,
        config=agent_config,
    )

    terminal_message("success", f"Orchestrator is created.")

    # 4. Loop over incoming tasks
    for step_index, step_config in enumerate(data_config["steps"], start=1):

        task_id = step_config.get("task_id", f"step_{step_index:02d}")

        incoming_table = load_table(
            table_path=step_config["path"],
            sample_num=step_config.get("sample_num", 0),
        )

        terminal_message("success", f"Task {task_id} load incoming table with keys: {incoming_table.keys()}.")

        existing_rdb = orchestrator.run_task(task_id, incoming_table)

        terminal_message("success", f"Task {task_id} running finished")

    # 5. Finish run
    # orchestrator.run_state.finish_run()
    orchestrator.save_state(Path(save_root_path) / "run_state.json")

    terminal_message("success", f"Run state is saved at {Path(save_root_path) / 'run_state.json'}.")

    # # 6. Save final run state / updated RDB / task results
    # output_dir = Path(config["output_dir"])
    # output_dir.mkdir(parents=True, exist_ok=True)

    # save_run_state(
    #     run_state=orchestrator.run_state,
    #     output_dir=output_dir,
    # )

    save_path = save_rdb(existing_rdb, save_root_path, folder_name="database")

    terminal_message("success", f"Relational database is saved at {save_path}.")
