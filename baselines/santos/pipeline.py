from baselines.discovery.pipeline import run_discovery_pipeline
from baselines.santos.model.matcher import SantosMatcher


def run_pipeline(data_config_path: str, agent_config_path: str, save_root_path: str) -> None:
    run_discovery_pipeline(
        method="santos",
        matcher=SantosMatcher,
        data_config_path=data_config_path,
        agent_config_path=agent_config_path,
        save_root_path=save_root_path,
    )
