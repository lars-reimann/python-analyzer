import argparse
import json
from argparse import _SubParsersAction
from pathlib import Path

from .utils import ensure_file_exists
from .commands.get_public_api import get_public_api
from .commands.improve import count_calls_and_parameters

__API_COMMAND = "api"
__COUNT_COMMAND = "count"
__IMPROVE_COMMAND = "improve"


def cli() -> None:
    args = __get_args()

    if args.command == __API_COMMAND:
        public_api = get_public_api(args.package)

        out_dir: Path = args.out
        out_file = out_dir.joinpath(f"{public_api.distribution}__{public_api.package}__{public_api.version}.json")
        ensure_file_exists(out_file)
        with out_file.open("w") as f:
            json.dump(public_api.to_json(), f, indent=4)
    elif args.command == __COUNT_COMMAND:
        pass
    elif args.command == __IMPROVE_COMMAND:
        count_calls_and_parameters(args.src, args.exclude, args.out)


def __get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Python code.")

    # Commands
    subparsers = parser.add_subparsers(dest="command")
    __add_api_subparser(subparsers)
    __add_count_subparser(subparsers)
    __add_improve_subparser(subparsers)

    return parser.parse_args()


def __add_api_subparser(subparsers: _SubParsersAction) -> None:
    improve_parser = subparsers.add_parser(
        __API_COMMAND,
        help="List the public API of a package."
    )
    improve_parser.add_argument(
        "-p",
        "--package",
        help="The name of the package. It must be installed in the current interpreter.",
        type=str,
        required=True,
    )
    improve_parser.add_argument(
        "-o", "--out", help="Output directory.", type=Path, required=True
    )


def __add_count_subparser(subparsers: _SubParsersAction) -> None:
    pass


def __add_improve_subparser(subparsers: _SubParsersAction) -> None:
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
