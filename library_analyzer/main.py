import argparse
import time
from pathlib import Path

from .call_and_parameter_counter import count_calls_and_parameters


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Python code.")
    subparsers = parser.add_subparsers(dest="command")

    # count command
    count_parser = subparsers.add_parser(
        "count",
        help="Count how often functions are called/parameters are used and with which values."
    )
    count_parser.add_argument(
        "-s",
        "--src",
        help="Directory containing Python code.",
        type=Path,
        required=True,
    )
    count_parser.add_argument(
        "-e",
        "--exclude",
        help="File with list of file names to exclude. Gets updated as Python source files are processed.",
        type=Path,
        required=True,
    )
    count_parser.add_argument(
        "-o", "--out", help="Output file.", type=Path, required=True
    )

    return parser.parse_args()


def main() -> None:
    args = get_args()

    start_time = time.time()

    if args.command == "count":
        count_calls_and_parameters(args.src, args.exclude, args.out)

    print("\n====================================================================================================")
    print(f"Program ran in {time.time() - start_time}s")
