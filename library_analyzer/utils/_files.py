import os
from pathlib import Path
from typing import TextIO


def list_python_files(root_dir: Path) -> list[str]:
    """
    :param root_dir: The directory containing the Python files.
    :return: A list with absolute paths to the Python files.
    """

    result: list[str] = []

    for root, _, files in os.walk(root_dir):
        for filename in files:
            if filename.endswith(".py"):
                result.append(str(os.path.join(root, filename)))

    return result


def initialize_and_read_exclude_file(exclude_file: Path) -> list[str]:
    exclude_file.parent.mkdir(parents=True, exist_ok=True)
    with exclude_file.open("r+") as f:
        return _read_lines(f)


def _read_lines(f: TextIO) -> list[str]:
    return [it.strip() for it in f.readlines() if it != ""]


def _write_lines(f: TextIO, lines: list[str]) -> None:
    f.writelines(f"{it}\n" for it in lines)
