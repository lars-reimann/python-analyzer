import importlib
from pathlib import Path
from typing import Optional

import astroid

from .utils import list_files, ASTWalker

# Type aliases
CallableStore = dict[str, dict[str, Optional[str]]]


def get_public_api(package_name: str) -> tuple[CallableStore, set[str]]:
    root = _package_root(package_name)
    files = list_files(root, ".py")
    files = _init_files_first(files)

    callable_visitor = _CallableVisitor()
    walker = ASTWalker(callable_visitor)
    for file in files:
        posix_path = Path(file).as_posix()
        print(f"Working on file {posix_path}")

        if _is_test_file(posix_path):
            print("Skipping test file.")
            continue

        with open(file, "r") as f:
            source = f.read()
            walker.walk(
                astroid.parse(
                    source,
                    module_name=_module_name(root, Path(file)),
                    path=file
                )
            )

    return callable_visitor.callables, callable_visitor.classes


def _package_root(package_name: str) -> Path:
    path_as_string = importlib.import_module(package_name).__file__
    return Path(path_as_string).parent


def _init_files_first(files: list[str]) -> list[str]:
    init_files = []
    other_files = []

    for file in files:
        if file.endswith("__init__.py"):
            init_files.append(file)
        else:
            other_files.append(file)

    return init_files + other_files


def _is_test_file(posix_path: str) -> bool:
    return "/test/" in posix_path or "/tests/" in posix_path


def _module_name(root: Path, file: Path) -> str:
    relative_path = file.relative_to(root.parent).as_posix()
    return str(relative_path).replace(".py", "").replace("/", ".")


class _CallableVisitor:
    def __init__(self) -> None:
        self.reexported: set[str] = set()
        self.callables: CallableStore = {}
        self.classes: set[str] = set()

    def visit_module(self, module_node: astroid.Module):
        if not _is_init_file(module_node.file):
            return

        for _, global_declaration_node_list in module_node.globals.items():
            global_declaration_node = global_declaration_node_list[0]

            if isinstance(global_declaration_node, astroid.ImportFrom):
                base_import_path = module_node.relative_to_absolute_name(
                    global_declaration_node.modname,
                    global_declaration_node.level
                )

                for declaration, _ in global_declaration_node.names:
                    reexported_name = f"{base_import_path}.{declaration}"

                    if reexported_name.startswith(module_node.name):
                        self.reexported.add(reexported_name)

    def visit_classdef(self, node: astroid.ClassDef) -> None:
        qname = node.qname()

        if self.is_public(node.name, qname):
            self.classes.add(qname)

    def visit_functiondef(self, node: astroid.FunctionDef) -> None:
        qname = node.qname()

        if self.is_public(node.name, qname):
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
            if name != "self"
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

    def is_public(self, name: str, qualified_name: str) -> bool:
        if name.startswith("_") and not name.endswith("__"):
            return False

        if qualified_name in self.reexported:
            return True

        return all(not it.startswith("_") for it in qualified_name.split("."))


def _is_init_file(path: str) -> bool:
    return path.endswith("__init__.py")
