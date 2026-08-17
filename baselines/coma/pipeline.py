from baselines.traditional.pipeline import run_traditional_pipeline


def run_pipeline(data_config_path: str, agent_config_path: str, save_root_path: str) -> None:
    run_traditional_pipeline(
        method="coma",
        data_config_path=data_config_path,
        agent_config_path=agent_config_path,
        save_root_path=save_root_path,
    )
