import argparse
import json
from argparse import _SubParsersAction
from pathlib import Path

from .commands.find_usages import find_usages
from .commands.get_api import distribution, distribution_version, get_api
from .commands.suggest_improvements import suggest_improvements
from .utils import ensure_file_exists

__API_COMMAND = "api"
__USAGES_COMMAND = "usages"
__IMPROVE_COMMAND = "improve"


def cli() -> None:
    args = __get_args()

    if args.command == __API_COMMAND:
        public_api = get_api(args.package)

        out_dir: Path = args.out
        out_file = out_dir.joinpath(f"{public_api.distribution}__{public_api.package}__{public_api.version}__api.json")
        ensure_file_exists(out_file)
        with out_file.open("w") as f:
            json.dump(public_api.to_json(), f, indent=2)

    elif args.command == __USAGES_COMMAND:
        usages = find_usages(args.package, args.src, args.tmp)

        dist = distribution(args.package)

        out_dir: Path = args.out
        out_file = out_dir.joinpath(
            f"{dist}__{args.package}__{distribution_version(dist)}__usages.json"
        )
        ensure_file_exists(out_file)
        with out_file.open("w") as f:
            json.dump(usages.to_json(), f, indent=2)

    elif args.command == __IMPROVE_COMMAND:
        suggest_improvements(args.api, args.usages, args.out, args.min)


def __get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Python code.")

    # Commands
    subparsers = parser.add_subparsers(dest="command")
    __add_api_subparser(subparsers)
    __add_usages_subparser(subparsers)
    __add_improve_subparser(subparsers)

    return parser.parse_args()


def __add_api_subparser(subparsers: _SubParsersAction) -> None:
    api_parser = subparsers.add_parser(
        __API_COMMAND,
        help="List the API of a package."
    )
    api_parser.add_argument(
        "-p",
        "--package",
        help="The name of the package. It must be installed in the current interpreter.",
        type=str,
        required=True,
    )
    api_parser.add_argument(
        "-o",
        "--out",
        help="Output directory.",
        type=Path,
        required=True
    )


def __add_usages_subparser(subparsers: _SubParsersAction) -> None:
    usages_parser = subparsers.add_parser(
        __USAGES_COMMAND,
        help="Find usages of API elements."
    )
    usages_parser.add_argument(
        "-p",
        "--package",
        help="The name of the package. It must be installed in the current interpreter.",
        type=str,
        required=True,
    )
    usages_parser.add_argument(
        "-s",
        "--src",
        help="Directory containing Python code.",
        type=Path,
        required=True,
    )
    usages_parser.add_argument(
        "-t",
        "--tmp",
        help="Directory where temporary files can be stored (to save progress in case the program crashes).",
        type=Path,
        required=True,
    )
    usages_parser.add_argument(
        "-o",
        "--out",
        help="Output directory.",
        type=Path,
        required=True
    )

def __add_improve_subparser(subparsers: _SubParsersAction) -> None:
    improve_parser = subparsers.add_parser(
        __IMPROVE_COMMAND,
        help="Suggest how to improve an existing API."
    )
    improve_parser.add_argument(
        "-a",
        "--api",
        help="File created by the 'api' command.",
        type=argparse.FileType('r'),
        required=True,
    )
    improve_parser.add_argument(
        "-u",
        "--usages",
        help="File created by the 'usages' command.",
        type=argparse.FileType('r'),
        required=True,
    )
    improve_parser.add_argument(
        "-o",
        "--out",
        help="Output directory.",
        type=Path,
        required=True
    )
    improve_parser.add_argument(
        "-m",
        "--min",
        help="Minimum number of usages required to keep an API element.",
        type=int,
        required=False,
        default=1
    )
