import importlib
from pathlib import Path
from typing import Optional

import astroid

from .utils import list_files, ASTWalker

# Type aliases
CallableStore = dict[str, dict[str, Optional[str]]]


def list_all_callables(package_name: str) -> CallableStore:
    root = _package_root(package_name)
    files = list_files(root, ".py")

    callable_visitor = _CallableVisitor()
    for file in files:
        callable_visitor.qname_root = _qname_root(root, Path(file))
        with open(file, "r") as f:
            source = f.read()
            ASTWalker(callable_visitor).walk(astroid.parse(source))

    return callable_visitor.callables


def _package_root(package_name: str) -> Path:
    path_as_string = importlib.import_module(package_name).__file__
    return Path(path_as_string).parent


def _qname_root(root: Path, file: Path) -> str:
    relative_path = file.relative_to(root.parent).as_posix()
    return str(relative_path).replace(".py", "").replace("/", ".")


class _CallableVisitor:
    def __init__(self) -> None:
        self.qname_root: str = ""
        self.callables: CallableStore = {}

    def visit_functiondef(self, node: astroid.FunctionDef) -> None:
        qname = f"{self.qname_root}{node.qname()}"

        if self.is_relevant(node.name, qname):
            print(f"Working on function {qname}")

            if qname not in self.callables:
                self.callables[qname] = self._function_parameters(node)

    @staticmethod
    def _function_parameters(node: astroid.FunctionDef) -> dict[str, Optional[str]]:
        parameters: astroid.Arguments = node.args
        n_implicit_parameters = node.implicit_parameters()

        result = [(it.name, None) for it in parameters.posonlyargs]
        result += [
            (
                it.name,
                _CallableVisitor._parameter_default(
                    parameters.defaults,
                    index - len(parameters.args) + len(parameters.defaults)
                )
            )
            for index, it in enumerate(parameters.args)
        ]
        result += [
            (
                it.name,
                _CallableVisitor._parameter_default(
                    parameters.kw_defaults,
                    index - len(parameters.kwonlyargs) + len(parameters.kw_defaults)
                )
            )
            for index, it in enumerate(parameters.kwonlyargs)
        ]

        return {
            name: default
            for name, default in result[n_implicit_parameters:]
        }

    @staticmethod
    def _parameter_default(defaults: list[astroid.NodeNG], default_index: int) -> Optional[str]:
        if 0 <= default_index < len(defaults):
            default = defaults[default_index]
            if default is None:
                return None
            return default.as_string()
        else:
            return None

    @staticmethod
    def is_relevant(name: str, qname: str) -> bool:
        if any(it in qname for it in ["._mocking.", "._testing.", ".tests."]):
            return False

        return not name.startswith("_") or name.startswith("__")
