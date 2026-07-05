import argparse
from pathlib import Path

from model.pipeline import run_pipeline

"""
python main.py --output "save/small_case_D_project_columns" --data-config "data/Chinook/benchmarks/small_case_D_project_columns/config.yaml" --agent-config "configs/single_llm.yaml"
python main.py --output "save/small_case_A_remove_columns" --data-config "data/Chinook/benchmarks/small_case_A_remove_columns/config.yaml" --agent-config "configs/single_llm.yaml"
nohup python main.py --data-config "data/Chinook/benchmarks/small_case_A_remove_columns/config.yaml" --agent-config "configs/single_llm.yaml"  > logs/output.log 2>&1 &
"""
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the pipeline over ordered incoming tables."
    )

    # parser.add_argument(
    #     "--existing-rdb",
    #     required=True,
    #     help="Path to the initial existing RDB folder or schema files.",
    # )

    parser.add_argument(
        "--output",
        required=True,
        help="Path to save the final updated RDB and run outputs.",
    )

    # parser.add_argument(
    #     "--tasks",
    #     required=True,
    #     help="Path to the task manifest YAML/JSON file.",
    # )

    parser.add_argument(
        "--agent-config",
        default=None,
        help="Optional path to agent configuration file.",
    )

    parser.add_argument(
        "--data-config",
        default=None,
        help="Optional path to data configuration file.",
    )

    # parser.add_argument(
    #     "--save-after-each-task",
    #     action="store_true",
    #     help="Save current existing RDB after each task.",
    # )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_pipeline(
        data_config_path=args.data_config,
        agent_config_path=args.agent_config,
        save_root_path=args.output
    )


if __name__ == "__main__":
    main()