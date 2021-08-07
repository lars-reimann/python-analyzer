import importlib
import json
from pathlib import Path

import astroid

from utils import list_files, ASTWalker


def list_all_callables(package_name: str):
    root = _package_root(package_name)
    files = list_files(root, ".py")

    callable_visitor = _CallableVisitor()
    for file in files:
        callable_visitor.qname_root = _qname_root(root, Path(file))
        with open(file, "r") as f:
            source = f.read()
            ASTWalker(callable_visitor).walk(astroid.parse(source))

    print(len(callable_visitor.callables.keys()))


def _package_root(package_name: str) -> Path:
    path_as_string = importlib.import_module(package_name).__file__
    return Path(path_as_string).parent


def _qname_root(root: Path, file: Path) -> str:
    relative_path = file.relative_to(root.parent).as_posix()
    return str(relative_path).replace(".py", "").replace("/", ".")


class _CallableVisitor:
    def __init__(self) -> None:
        self.qname_root: str = ""
        self.callables: dict[str, dict[str, str]] = {}

    def visit_functiondef(self, node: astroid.FunctionDef) -> None:
        qname = f"{self.qname_root}{node.qname()}"

        if self.is_relevant(node.name, qname):
            print(f"Working on function {qname}")

            if qname not in self.callables:
                self.callables[qname] = {}

    @staticmethod
    def is_relevant(name: str, qname: str) -> bool:
        if any(it in qname for it in ["._mocking.", "._testing.", ".tests."]):
            return False

        return not name.startswith("_") or name.startswith("__")


if __name__ == '__main__':
    list_all_callables("sklearn")
