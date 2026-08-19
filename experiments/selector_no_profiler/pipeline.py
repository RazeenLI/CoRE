from __future__ import annotations
import yaml
from experiments.selector_no_profiler.model.selector import CandidateSelector
from experiments.selector_no_profiler.model.pipeline import run_selector_pipeline
def run_pipeline(
    data_config_path: str,
    agent_config_path: str,
    save_root_path: str,
) -> None:
    with open(agent_config_path, "r", encoding="utf-8") as file:
        agent_config = yaml.safe_load(file)
    config = agent_config.get("selector_no_profiler", {})
    selector = CandidateSelector(
        embedding_model_name=config.get(
            "embedding_model",
            "sentence-transformers/all-mpnet-base-v2",
        ),
        column_top_k=config.get("column_top_k", 20),
        table_top_k=config.get("table_top_k", 5),
    )
    run_selector_pipeline(
        data_config_path=data_config_path,
        agent_config_path=agent_config_path,
        save_root_path=save_root_path,
        selector=selector,
    )
