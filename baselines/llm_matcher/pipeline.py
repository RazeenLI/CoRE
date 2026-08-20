# run_pipeline.py
import torch
import argparse
from pathlib import Path

import pandas as pd
import yaml

from model.utils.io import load_rdb, save_rdb, load_table, terminal_message, save_json

from model.core.llm_client import HFLLMClient

from model.agents.base_agent import BaseAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.validator_agent import ValidatorAgent

from baselines.llm_matcher.model.matcher_agent import MatcherAgent
from baselines.llm_matcher.model.evolutor_agent import EvolutorAgent

from baselines.llm_matcher.model.orchestrator import Orchestrator

# from agents.decision import DecisionAgent


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

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
    # decision_agent = BaseAgent(llm_client)

    return {
        "profiler": profiler_agent,
        "matcher": matcher_agent,
        "evolutor": evolutor_agent,
        "validator": validator_agent,
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
    
    # 3. Create agents
    agents = create_agents(llm_client)

    terminal_message("success", f"LLM Client and Agents are created.")

    # 3. Create orchestrator
    orchestrator = Orchestrator(
        profiler_agent=agents["profiler"],
        matcher_agent=agents["matcher"],
        evolutor_agent=agents["evolutor"],
        validator_agent=agents["validator"],
        save_path=save_root_path,
        config=agent_config["orchestrator"],
    )

    terminal_message("success", f"Orchestrator is created.")

    # only one incoming table new

    steps = data_config["steps"]
    if len(steps) != 1:
        raise ValueError(f"Exactly one incoming table is required, got {len(steps)}.")

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

    existing_rdb = task_state.existing_rdb  # Update existing RDB for the next task

    terminal_message("success", f"Task {task_id} running finished")

    # 5. Finish run, save state and proposal
    save_json(task_state.to_dict(), Path(save_root_path) / "task_state.json",)

    terminal_message("success", f"Task state is saved at {Path(save_root_path) / 'task_state.json'}.")

    save_json(proposal, Path(save_root_path) / "proposal.json")

    terminal_message("success", f"Proposal is saved at {Path(save_root_path) / 'proposal.json'}.")

    save_path = save_rdb(existing_rdb, save_root_path, folder_name="database")

    terminal_message("success", f"Relational database is saved at {save_path}.")
