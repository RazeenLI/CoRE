#!/usr/bin/env python3

import argparse
from pathlib import Path

"""
python check_results.py \
    --output-root save/Chinook/oneshot/medium \
    --result-name proposal.json
"""


def find_missing_results(
    output_root: Path,
    result_name: str = "result",
) -> list[Path]:
    """
    Check every case directory under output_root.

    A case is considered complete when it contains a file or directory
    named result_name.
    """
    if not output_root.exists():
        raise FileNotFoundError(f"Output root does not exist: {output_root}")

    if not output_root.is_dir():
        raise NotADirectoryError(f"Output root is not a directory: {output_root}")

    case_dirs = sorted(
        path
        for path in output_root.glob("case*")
        if path.is_dir()
    )

    if not case_dirs:
        print(f"[Warning] No case directories found under: {output_root}")
        return []

    missing_cases: list[Path] = []

    for case_dir in case_dirs:
        result_path = case_dir / result_name

        if not result_path.exists():
            missing_cases.append(case_dir)

    return missing_cases


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check which output case folders do not contain a result."
    )

    parser.add_argument(
        "--output-root",
        required=True,
        type=Path,
        help="Root directory containing case output folders.",
    )

    parser.add_argument(
        "--result-name",
        default="result",
        help="Expected result file or directory name. Default: result",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        missing_cases = find_missing_results(
            output_root=args.output_root,
            result_name=args.result_name,
        )
    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"[Error] {error}")
        raise SystemExit(1) from error

    if not missing_cases:
        print(
            f"[Success] Every case folder contains "
            f"'{args.result_name}'."
        )
        return

    print(
        f"[Missing] {len(missing_cases)} case folder(s) do not contain "
        f"'{args.result_name}':"
    )

    for case_dir in missing_cases:
        print(f"  - {case_dir}")

    raise SystemExit(1)


if __name__ == "__main__":
    main()