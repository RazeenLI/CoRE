import argparse
from importlib import import_module
from typing import Callable


PIPELINE_MODULES = {
    "standard": "model.pipeline",
    "grain_profiler": "experiments.grain_profiler.pipeline",
    "constraint_filter": "experiments.constraint_filter.pipeline",
    "validator_prompt": "experiments.validator_prompt.pipeline",
    "no_values": "experiments.no_values.pipeline",
    "no_profiler": "baselines.no_profiler.pipeline",
    "no_selector": "baselines.no_selector.pipeline",
    "no_validator": "baselines.no_validator.pipeline",
    "llm_matcher": "baselines.llm_matcher.pipeline",
    "oneshot": "baselines.oneshot.pipeline",
    "magneto": "baselines.magneto.pipeline",
    "magneto_llm": "baselines.magneto_llm.pipeline",
    "santos": "baselines.santos.pipeline",
    "embdi": "baselines.embdi.pipeline",
    "starmie": "baselines.starmie.pipeline",
    "jl": "baselines.jl.pipeline",
    "coma": "baselines.coma.pipeline",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an RDB integration pipeline over ordered incoming tables."
    )

    parser.add_argument(
        "--model",
        default="standard",
        choices=PIPELINE_MODULES.keys(),
        help="Pipeline model to run.",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to save the final updated RDB and run outputs.",
    )

    parser.add_argument(
        "--agent-config",
        required=True,
        help="Path to the agent configuration YAML file.",
    )

    parser.add_argument(
        "--data-config",
        required=True,
        help="Path to the dataset configuration YAML file.",
    )

    return parser.parse_args()


def get_run_pipeline(model_name: str) -> Callable:
    """
    Load the run_pipeline function corresponding to the selected model.
    """
    module_path = PIPELINE_MODULES[model_name]
    pipeline_module = import_module(module_path)

    run_pipeline = getattr(pipeline_module, "run_pipeline", None)

    if run_pipeline is None or not callable(run_pipeline):
        raise ImportError(
            f"Module '{module_path}' does not define a callable run_pipeline function."
        )

    return run_pipeline


def main() -> None:
    args = parse_args()

    run_pipeline = get_run_pipeline(args.model)

    run_pipeline(
        data_config_path=args.data_config,
        agent_config_path=args.agent_config,
        save_root_path=args.output,
    )


if __name__ == "__main__":
    main()
