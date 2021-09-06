import argparse
from pathlib import Path

from .improve_command import count_calls_and_parameters

__IMPROVE_COMMAND = "improve"

def cli() -> None:
    args = __get_args()

    if args.command == __IMPROVE_COMMAND:
        count_calls_and_parameters(args.src, args.exclude, args.out)


def __get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Python code.")
    subparsers = parser.add_subparsers(dest="command")

    # improve command
    improve_parser = subparsers.add_parser(
        __IMPROVE_COMMAND,
        help="Suggest how to improve an existing API."
    )
    improve_parser.add_argument(
        "-s",
        "--src",
        help="Directory containing Python code.",
        type=Path,
        required=True,
    )
    improve_parser.add_argument(
        "-e",
        "--exclude",
        help="File with list of file names to exclude. Gets updated as Python source files are processed.",
        type=Path,
        required=True,
    )
    improve_parser.add_argument(
        "-o", "--out", help="Output file.", type=Path, required=True
    )

    return parser.parse_args()
