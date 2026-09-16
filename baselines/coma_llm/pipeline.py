from typing import Any

import yaml

from baselines.llm_adapter.pipeline import run_llm_adapter_pipeline
from baselines.traditional.model.matcher import MatcherConfig, TraditionalMatcher


def run_pipeline(
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    with open(agent_config_path, "r", encoding="utf-8") as file:
        agent_config: dict[str, Any] = yaml.safe_load(file)
    config = {
        **agent_config.get("traditional", {}),
        **agent_config.get("coma", {}),
    }
    matcher = TraditionalMatcher(
        method="coma",
        config=MatcherConfig(
            assignment_threshold=config.get("assignment_threshold", 0.70),
            coma_use_schema=config.get("use_schema", True),
            coma_use_instances=config.get("use_instances", True),
            coma_delta=config.get("delta", 0.15),
        ),
    )
    run_llm_adapter_pipeline(
        method="coma",
        matcher=matcher,
        data_config_path=data_config_path,
        agent_config_path=agent_config_path,
        save_root_path=save_root_path,
    )
