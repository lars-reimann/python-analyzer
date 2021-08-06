import os
from pathlib import Path


def list_python_files(root_dir: Path) -> list[str]:
    result: list[str] = []

    for root, _, files in os.walk(root_dir):
        for filename in files:
            if filename.endswith(".py"):
                result.append(str(os.path.join(root, filename)))

    return result
