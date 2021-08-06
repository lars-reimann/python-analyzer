import concurrent.futures as promises
import multiprocessing
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Optional, Any, Generator

import astroid
from astroid.arguments import CallSite
from astroid.helpers import safe_infer

from .utils import ASTWalker, list_python_files, initialize_and_read_exclude_file


class CallAndParameterCounter:
    def __init__(self) -> None:
        self.call_counter: Counter[str, int] = Counter()
        self.parameter_counter: dict[str, Counter[str, int]] = {}

    # noinspection PyMethodMayBeStatic
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

        # Count how often each method is called
        self.call_counter[qualified_name] += 1

        # Count how often each parameter is used
        if qualified_name not in self.parameter_counter:
            self.parameter_counter[qualified_name] = Counter({
                name: 0
                for name in _all_parameter_names(parameters, n_implicit_parameters)
            })

        for parameter_name in bound_parameters.keys():
            self.parameter_counter[qualified_name][parameter_name] += 1

        # TODO: find values that are commonly used


def _analyze_declaration_called_by(node: astroid.Call) -> Optional[tuple[str, astroid.Arguments, int]]:
    """
    Returns None if the called declaration could not be determined or if it is not relevant for us. Otherwise, it
    returns a tuple with the form (qualified_name, parameters, n_implicit_parameters).
    """

    called = safe_infer(node.func)
    if called is None or isinstance(called, astroid.Lambda) or not _is_relevant(called.qname()):
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


def _is_relevant(qualified_name: str) -> bool:
    return any(qualified_name.startswith(prefix) for prefix in relevant_prefixes)


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


if __name__ == '__main__':
    start_time = time.time()

    # TODO run in loop for all file
    # TODO catch exceptions on current file to continue run
    # TODO save progress after each file
    # TODO save line numbers & files of calls
    # TODO save all stats about kernels (hotness, votes, dates, uses etc.)
    parse_tree = astroid.parse(test2)
    call_and_parameter_counter = CallAndParameterCounter()
    ASTWalker(call_and_parameter_counter).walk(parse_tree)

    print("===== Call counter =================================================================================")
    for callable_qualified_name, count in call_and_parameter_counter.call_counter.items():
        print(f"{callable_qualified_name}: {count}")
    print()

    print("===== Parameter counter ============================================================================")
    for (callable_qualified_name, counter) in call_and_parameter_counter.parameter_counter.items():
        print(f"{callable_qualified_name}:")
        for parameter_name, count in counter.items():
            print(f"   {parameter_name}: {count}")
    print()

    print("====================================================================================================")
    print(f"Program ran in {time.time() - start_time}s")

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


def count_calls_and_parameters(src_dir: Path, exclude_file: Path, out: Path):
    candidate_python_files = list_python_files(src_dir)
    excluded_python_files = set(initialize_and_read_exclude_file(exclude_file))
    python_files = [it for it in candidate_python_files if it not in excluded_python_files]

    length = len(python_files)
    lock = multiprocessing.Lock()
    with promises.ProcessPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(do_count_calls_and_parameters, python_file, exclude_file, out, index, length, lock)
            for index, python_file in enumerate(python_files)
        ]
        print("waiting")
        promises.wait(futures)
        # merge results together (reducer)
    # print(python_files)

    # use this for the progress update 1/77000...
    # print current file name
    # initialize with old excluded stuff from exclude_file
    # initialize with previous counter
    # go through each file
    # make sure nothing crashes (catch exceptions)
    # count calls, parameters uses, individual values for parameters
    # keep track of line numbers
    # update out file
    # update excluded
    # run analysis in parallel (Pool, threading, multiprocessing => concurrent.futures)


def do_count_calls_and_parameters(
    python_file: str,
    exclude_file: Path,
    out: Path,
    index: int,
    length: int,
    lock: multiprocessing.Lock
):
    with lock:
        print(f"Working on {python_file} ({index}/{length})")
        index += 1

    with lock:
        with exclude_file.open("a") as f:
            f.write(f"{python_file}\n")
