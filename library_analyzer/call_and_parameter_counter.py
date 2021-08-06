import json
import multiprocessing
import sys
from pathlib import Path
from typing import Optional, Any, Generator

import astroid
from astroid.arguments import CallSite
from astroid.helpers import safe_infer

from .utils import ASTWalker, list_python_files, initialize_and_read_exclude_file

relevant_prefixes = {
    # "bokeh",
    # "catboost",
    # "cntk",
    # "eli5",
    # "gym",
    # "keras",
    # "lightgbm",
    # "matplotlib",
    # "nltk"
    # "numpy",
    # "pandas",
    # "plotly",
    # "pydot",
    # "scipy",
    # "seaborn",
    "sklearn",
    # "spacy",
    # "statsmodels",
    # "tensorflow",
    # "torch",
    # "xgboost"
}


def count_calls_and_parameters(src_dir: Path, exclude_file: Path, out_dir: Path):
    candidate_python_files = list_python_files(src_dir)
    excluded_python_files = set(initialize_and_read_exclude_file(exclude_file))
    python_files = [it for it in candidate_python_files if it not in excluded_python_files]

    out_dir.mkdir(parents=True, exist_ok=True)

    length = len(python_files)
    lock = multiprocessing.Lock()
    with multiprocessing.Pool(initializer=initialize_process_environment, initargs=(lock,)) as pool:
        for index, python_file in enumerate(python_files):
            pool.apply(do_count_calls_and_parameters, [python_file, exclude_file, out_dir, index, length])

    pool.join()

    # TODO merge results together (reducer)


def initialize_process_environment(lock: multiprocessing.Lock):
    # noinspection PyGlobalUndefined
    global _lock
    _lock = lock


def do_count_calls_and_parameters(
    python_file: str,
    exclude_file: Path,
    out_dir: Path,
    index: int,
    length: int,
):
    with _lock:
        print(f"Working on {python_file} ({index + 1}/{length})")
        index += 1

    with open(python_file, "r") as f:
        source = f.read()

    if _is_relevant_python_file(source):
        # TODO make sure nothing crashes (catch exceptions)

        call_and_parameter_counter = _CallAndParameterCounter(python_file)
        ASTWalker(call_and_parameter_counter).walk(astroid.parse(source))

        out_file = out_dir.joinpath(python_file.replace("/", "$$$").replace("\\", "$$$").replace(".py", ".json"))
        with out_file.open("w") as f:
            json.dump({
                "calls": call_and_parameter_counter.calls,
                "parameters": call_and_parameter_counter.parameters,
                "values": call_and_parameter_counter.values
            }, f, indent=4)
    else:
        print("Skipping irrelevant file")

    with _lock:
        with exclude_file.open("a") as f:
            f.write(f"{python_file}\n")


def _is_relevant_qualified_name(qualified_name: str) -> bool:
    return any(qualified_name.startswith(prefix) for prefix in relevant_prefixes)


def _is_relevant_python_file(source: str) -> bool:
    return any(prefix in source for prefix in relevant_prefixes)


CallableName = str
ParameterName = str
StringifiedValue = str
FileName = str
LineNumber = int
ColumnNumber = int
Occurrence = tuple[FileName, Optional[LineNumber], Optional[ColumnNumber]]
CallStore = dict[CallableName, list[Occurrence]]
ParameterStore = dict[CallableName, dict[ParameterName, list[Occurrence]]]
ValueStore = dict[CallableName, dict[ParameterName, dict[StringifiedValue, list[Occurrence]]]]


class _CallAndParameterCounter:
    def __init__(self, python_file: str) -> None:
        self.python_file: str = python_file
        self.calls: CallStore = {}
        self.parameters: ParameterStore = {}
        self.values: ValueStore = {}

    def visit_call(self, node: astroid.Call):
        called = _analyze_declaration_called_by(node)
        if called is None:
            return
        qualified_name, parameters, n_implicit_parameters = called

        bound_parameters = _bound_parameters(
            parameters,
            CallSite.from_call(node),
            n_implicit_parameters
        )
        if bound_parameters is None:
            return

        occurrence: Occurrence = (self.python_file, node.lineno, node.col_offset)

        # Count how often each method is called
        if qualified_name not in self.calls:
            self.calls[qualified_name] = []
        self.calls[qualified_name].append(occurrence)

        # Count how often each parameter is used
        if qualified_name not in self.parameters:
            self.parameters[qualified_name] = {
                name: []
                for name in _all_parameter_names(parameters, n_implicit_parameters)
            }

        for parameter_name in bound_parameters.keys():
            self.parameters[qualified_name][parameter_name].append(occurrence)

        # Count how often each value is used
        if qualified_name not in self.values:
            self.values[qualified_name] = {
                name: {}
                for name in _all_parameter_names(parameters, n_implicit_parameters)
            }

        for parameter_name, value in bound_parameters.items():
            stringified_value = value.as_string()
            if stringified_value not in self.values[qualified_name][parameter_name]:
                self.values[qualified_name][parameter_name][stringified_value] = []

            self.parameters[qualified_name][parameter_name][stringified_value].append(occurrence)


def _analyze_declaration_called_by(node: astroid.Call) -> Optional[tuple[str, astroid.Arguments, int]]:
    """
    Returns None if the called declaration could not be determined or if it is not relevant for us. Otherwise, it
    returns a tuple with the form (qualified_name, parameters, n_implicit_parameters).
    """

    called = safe_infer(node.func)
    if called is None or isinstance(called, astroid.Lambda) or not _is_relevant_qualified_name(called.qname()):
        return None

    n_implicit_parameters = _n_implicit_parameters(called)

    if isinstance(called, astroid.ClassDef):
        called = _called_constructor(called)
        if called is None:
            return None

    if isinstance(called, (astroid.BoundMethod, astroid.UnboundMethod, astroid.FunctionDef)):
        return called.qname(), called.args, n_implicit_parameters
    else:
        return None


def _n_implicit_parameters(called: astroid.NodeNG) -> int:
    return called.implicit_parameters() if hasattr(called, "implicit_parameters") else 0


def _called_constructor(class_def: astroid.ClassDef) -> Optional[astroid.FunctionDef]:
    try:
        # Use last __new__
        new = class_def.local_attr("__new__")[-1]
    except astroid.NotFoundError:
        new = None

    new_is_from_object = new and new.parent.scope().name == "object"
    new_is_from_builtins = new and new.root().name in sys.builtin_module_names

    if new is None or new_is_from_object or new_is_from_builtins:
        try:
            # Use last __init__
            constructor = class_def.local_attr("__init__")[-1]
        except astroid.NotFoundError:
            return None
    else:
        constructor = new

    if isinstance(constructor, astroid.FunctionDef):
        return constructor
    else:
        return None


def _bound_parameters(
    parameters: astroid.Arguments,
    arguments: CallSite,
    n_implicit_parameters: int
) -> Optional[dict[str, Any]]:
    # Improper call
    if parameters.args is None or arguments.has_invalid_arguments() or arguments.has_invalid_keywords():
        return None

    result: dict[str, Any] = arguments.keyword_arguments.copy()

    positional_parameter_names = [it.name for it in (parameters.posonlyargs + parameters.args)][n_implicit_parameters:]

    for index, arg in enumerate(arguments.positional_arguments):
        result[positional_parameter_names[index]] = arg

    return result


def _all_parameter_names(parameters: astroid.Arguments, n_implicit_parameters: int) -> Generator[str, Any, None]:
    return (
        it.name
        for it in (parameters.posonlyargs + parameters.args + parameters.kwonlyargs)[n_implicit_parameters:]
    )
