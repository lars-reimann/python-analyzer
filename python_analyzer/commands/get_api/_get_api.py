from pathlib import Path

import astroid

from python_analyzer.utils import ASTWalker
from ._ast_visitor import _CallableVisitor
from ._file_filters import _is_test_file
from ._model import API
from ._package_metadata import distribution, distribution_version, package_files, package_root


def get_api(package_name: str) -> API:
    root = package_root(package_name)
    dist = distribution(package_name)
    dist_version = distribution_version(dist)
    files = package_files(package_name)

    api = API(dist, package_name, dist_version)
    callable_visitor = _CallableVisitor(api)
    walker = ASTWalker(callable_visitor)

    for file in files:
        posix_path = Path(file).as_posix()
        print(f"Working on file {posix_path}")

        if _is_test_file(posix_path):
            print("Skipping test file")
            continue

        with open(file, "r") as f:
            source = f.read()
            walker.walk(
                astroid.parse(
                    source,
                    module_name=__module_name(root, Path(file)),
                    path=file
                )
            )

    return callable_visitor.api


def __module_name(root: Path, file: Path) -> str:
    relative_path = file.relative_to(root.parent).as_posix()
    return str(relative_path).replace(".py", "").replace("/", ".")
