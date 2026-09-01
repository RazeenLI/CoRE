from baselines.discovery.pipeline import run_discovery_pipeline
from baselines.embdi.model.matcher import EmbDIMatcher


def run_pipeline(data_config_path: str, agent_config_path: str, save_root_path: str) -> None:
    run_discovery_pipeline(
        method="embdi",
        matcher=EmbDIMatcher,
        data_config_path=data_config_path,
        agent_config_path=agent_config_path,
        save_root_path=save_root_path,
    )
