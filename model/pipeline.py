# run_pipeline.py

import argparse
from pathlib import Path

import pandas as pd
import yaml

from model.utils.io import load_rdb, save_rdb, load_table

# from core.orchestrator import Orchestrator
# from core.task import IngestionTask
# from core.io import , save_run_state

from model.core.llm_client import HFLLMClient

from model.agents.profiler_agent import ProfilerAgent
# from agents.matcher import MatcherAgent
# from agents.evolution import EvolutionAgent
# from agents.validator import ValidatorAgent
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
    # matcher_agent = MatcherAgent(config=config)
    # evolution_agent = EvolutionAgent(config=config)
    # validator_agent = ValidatorAgent(config=config)
    # decision_agent = DecisionAgent(config=config)

    return {
        "profiler": profiler_agent,
        # "matcher": matcher_agent,
        # "evolution": evolution_agent,
        # "validator": validator_agent,
        # "decision": decision_agent,
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

    print(f"[Successed] Load existing relational database with keys: {existing_rdb.keys()}.")

    save_path = save_rdb(existing_rdb, save_root_path, folder_name="example")

    print(f"[Successed] relational database is saved at {save_path}.")

    # 2. Create LLM Client
    llm_client = HFLLMClient(model_name=agent_config["LLMs"]["name"])
    
    # 3. Create agents
    agents = create_agents(llm_client)

    # # 3. Create orchestrator
    # orchestrator = Orchestrator(
    #     profiler_agent=agents["profiler"],
    #     matcher_agent=agents["matcher"],
    #     evolution_agent=agents["evolution"],
    #     validator_agent=agents["validator"],
    #     decision_agent=agents["decision"],
    #     existing_rdb=existing_rdb,
    #     config=config,
    # )

    # 4. Loop over incoming tasks
    for step_index, step_config in enumerate(data_config["steps"], start=1):
        incoming_table = load_table(
            table_path=step_config["path"],
            sample_num=step_config.get("sample_num", 0),
        )

        task_id = step_config.get("task_id", f"step_{step_index:02d}")
        print(f"[Successed] Task {task_id} load incoming table with keys: {incoming_table.keys()}.")

        # task = {
        #     "task_id": task_id,
        #     "step_index": step_index,
        #     "incoming_path": step_config["path"],
        # }

        # existing_rdb = orchestrator.run_task(
        #     task=task,
        #     incoming_table=incoming_table,
        # )
        # task = load_incoming_task(step_config)
        # orchestrator.run_task(task)

    # # 5. Finish run
    # orchestrator.run_state.finish_run()

    # # 6. Save final run state / updated RDB / task results
    # output_dir = Path(config["output_dir"])
    # output_dir.mkdir(parents=True, exist_ok=True)

    # save_run_state(
    #     run_state=orchestrator.run_state,
    #     output_dir=output_dir,
    # )
