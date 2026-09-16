from typing import Any

import yaml

from baselines.llm_adapter.pipeline import run_llm_adapter_pipeline
from baselines.starmie.model.matcher import StarmieMatcher


def run_pipeline(
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    with open(agent_config_path, "r", encoding="utf-8") as file:
        agent_config: dict[str, Any] = yaml.safe_load(file)
    matcher = StarmieMatcher(agent_config.get("starmie", {}))
    run_llm_adapter_pipeline(
        method="starmie",
        matcher=matcher,
        data_config_path=data_config_path,
        agent_config_path=agent_config_path,
        save_root_path=save_root_path,
    )
