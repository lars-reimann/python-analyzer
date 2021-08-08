import json
import multiprocessing
import sys
from pathlib import Path
from typing import Optional, Any

import astroid
from astroid.arguments import CallSite
from astroid.helpers import safe_infer

from .all_callables_in_library import list_all_callables
from .utils import ASTWalker, list_files, initialize_and_read_exclude_file

# Type aliases
CallableName = str
ParameterName = str
StringifiedValue = str
FileName = str
LineNumber = int
ColumnNumber = int
Occurrence = tuple[FileName, Optional[LineNumber], Optional[ColumnNumber]]
CallStore = dict[CallableName, list[Occurrence]]
ParameterStore = dict[CallableName, dict[ParameterName, list[Occurrence]]]
ValueStore = dict[CallableName, dict[ParameterName, dict[str, Any]]]

# Global values
_relevant_packages = {
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
    candidate_python_files = list_files(src_dir, ".py")
    excluded_python_files = set(initialize_and_read_exclude_file(exclude_file))
    python_files = [it for it in candidate_python_files if it not in excluded_python_files]

    out_dir.mkdir(parents=True, exist_ok=True)

    length = len(python_files)

    lock = multiprocessing.Lock()
    with multiprocessing.Pool(processes=12, initializer=_initialize_process_environment, initargs=(lock,)) as pool:
        pool.starmap(
            _do_count_calls_and_parameters,
            [[it[1], exclude_file, out_dir, it[0], length] for it in enumerate(python_files)]
        )
    pool.join()

    (result_calls, result_parameters, result_values) = _merge_results(out_dir)
    _aggregate_results(out_dir, result_calls, result_parameters, result_values)


def _initialize_process_environment(lock: multiprocessing.Lock):
    # noinspection PyGlobalUndefined
    global _lock
    _lock = lock


def _do_count_calls_and_parameters(
    python_file: str,
    exclude_file: Path,
    out_dir: Path,
    index: int,
    length: int,
):
    with _lock:
        print(f"Working on {python_file} ({index + 1}/{length})")
        index += 1

    try:
        with open(python_file, "r") as f:
            source = f.read()

        if _is_relevant_python_file(source):
            call_and_parameter_counter = _CallAndParameterCounter(python_file)
            ASTWalker(call_and_parameter_counter).walk(astroid.parse(source))

            out_file = out_dir.joinpath(
                python_file.replace("/", "$$$").replace("\\", "$$$").replace(".py", ".json")
            )
            with out_file.open("w") as f:
                json.dump({
                    "calls": call_and_parameter_counter.calls,
                    "parameters": call_and_parameter_counter.parameters,
                    "values": call_and_parameter_counter.values
                }, f, indent=4)
        else:
            print(f"Skipping {python_file} (irrelevant file)")

    except UnicodeError:
        print(f"Skipping {python_file} (broken encoding)")
    except astroid.exceptions.AstroidSyntaxError:
        print(f"Skipping {python_file} (invalid syntax)")
    except RecursionError:
        print(f"Skipping {python_file} (infinite recursion)")

    with _lock:
        with exclude_file.open("a") as f:
            f.write(f"{python_file}\n")


def _merge_results(out_dir: Path) -> tuple[CallStore, ParameterStore, ValueStore]:
    result_calls: CallStore = {}
    result_parameters: ParameterStore = {}
    result_values: ValueStore = {}

    # Include all callables and parameters (and their default values) from relevant packages
    for package_name in _relevant_packages:
        callables = list_all_callables(package_name)

        for callable_name, parameters in callables.items():
            result_calls[callable_name] = []
            result_parameters[callable_name] = {}
            result_values[callable_name] = {}

            for parameter_name, default_value in parameters.items():
                result_parameters[callable_name][parameter_name] = []
                result_values[callable_name][parameter_name] = {
                    "defaultValue": default_value,
                    "values": {}
                }

    files = list_files(out_dir, ".json")
    for index, file in enumerate(files):
        if "$$$$$merged" in file:
            continue  # this is an output of this process

        print(f"Merging {file} ({index + 1}/{len(files)})")

        with open(file, "r") as f:
            content = json.load(f)

        # merge calls
        call_store: CallStore = content["calls"]
        for callable_name, occurrences in call_store.items():
            if callable_name not in result_calls:
                result_calls[callable_name] = []

            result_calls[callable_name].extend(occurrences)

        # merge parameters
        parameter_store: ParameterStore = content["parameters"]
        for callable_name, parameters in parameter_store.items():
            if callable_name not in result_parameters:
                result_parameters[callable_name] = {}

            for parameter_name, occurrences in parameters.items():
                if parameter_name not in result_parameters[callable_name]:
                    result_parameters[callable_name][parameter_name] = []

                result_parameters[callable_name][parameter_name].extend(occurrences)

        # merge values
        value_store: ValueStore = content["values"]
        for callable_name, parameters in value_store.items():
            if callable_name not in result_values:
                result_values[callable_name] = {}

            for parameter_name, values in parameters.items():
                if parameter_name not in result_values[callable_name]:
                    result_values[callable_name][parameter_name] = {
                        "defaultValue": None,
                        "values": {}
                    }

                for stringified_value, occurrences in values.items():
                    if stringified_value not in result_values[callable_name][parameter_name]["values"]:
                        result_values[callable_name][parameter_name]["values"][stringified_value] = []

                    result_values[callable_name][parameter_name]["values"][stringified_value].extend(occurrences)

    result_occurrences = {
        "calls": result_calls,
        "parameters": result_parameters,
        "values": result_values
    }

    with out_dir.joinpath("$$$$$merged_occurrences$$$$$.json").open("w") as f:
        json.dump(result_occurrences, f, indent=4)

    return result_calls, result_parameters, result_values


def _aggregate_results(out_dir: Path, result_calls: CallStore, result_parameters: ParameterStore,
                       result_values: ValueStore):
    call_counts, parameter_counts, value_counts = _count(out_dir, result_calls, result_parameters, result_values)
    _count_distribution(out_dir, call_counts, value_counts)


def _count(
    out_dir: Path,
    result_calls: CallStore,
    result_parameters: ParameterStore,
    result_values: ValueStore
) -> tuple[Any, Any, Any]:
    call_counts = {
        callable_name: len(occurrences)
        for callable_name, occurrences in result_calls.items()
    }

    parameter_counts = {
        callable_name: {
            # how often a parameter is set explicitly
            parameter_name: len(occurrences)
            for parameter_name, occurrences in parameters.items()
        }
        for callable_name, parameters in result_parameters.items()
    }

    value_counts = {
        callable_name: {
            parameter_name: {
                stringified_value:
                    len(occurrences)
                    if stringified_value != parameter_data["defaultValue"]
                    # how often the default value is used (explicitly or implicitly)
                    else call_counts[callable_name] - sum(
                        [
                            len(occurrences)
                            for inner_stringified_value, occurrences in parameter_data["values"].items()
                            if inner_stringified_value != parameter_data["defaultValue"]
                        ]
                    )
                for stringified_value, occurrences in parameter_data["values"].items()
            }
            for parameter_name, parameter_data in parameters.items()
        }
        for callable_name, parameters in result_values.items()
    }

    result_counts = {
        "calls": call_counts,
        "values": value_counts
    }

    with out_dir.joinpath("$$$$$merged_counts$$$$$.json").open("w") as f:
        json.dump(result_counts, f, indent=4)

    result_counts_compacts = {
        callable_name: {
            "count": call_counts[callable_name],
            "parameters": {
                parameter_name: {
                    "values": {
                        stringified_value: value_count
                        for stringified_value, value_count in sorted(
                            values.items(),
                            key=lambda it: it[1],
                            reverse=True
                        )
                    }
                }
                for parameter_name, values in sorted(
                    parameters.items(),
                    key=lambda it: parameter_counts[callable_name][it[0]],
                    reverse=True
                )
            }
        }
        for callable_name, parameters in sorted(
            value_counts.items(),
            key=lambda it: call_counts[it[0]],
            reverse=True
        )
    }

    with out_dir.joinpath("$$$$$merged_counts_compact$$$$$.json").open("w") as f:
        json.dump(result_counts_compacts, f, indent=4)

    return call_counts, parameter_counts, value_counts


def _count_distribution(out_dir: Path, call_counts: Any, value_counts: Any):
    # count classes that are used at most i times
    flat_class_instantiation_counts = [
        count
        for callable_name, count in call_counts.items()
        if callable_name.endswith("__init__")
    ]
    max_instantiation_count = max(flat_class_instantiation_counts)

    class_instantiated_at_most = []
    for i in range(max_instantiation_count + 1):
        class_instantiated_at_most_i_times = len([count for count in flat_class_instantiation_counts if count <= i])
        class_instantiated_at_most.append(class_instantiated_at_most_i_times)

    with out_dir.joinpath("$$$$$merged_class_instantiated_at_most_index_times$$$$$.json").open("w") as f:
        json.dump(
            [
                {"maxInstantiation": index, "classCount": count}
                for index, count in enumerate(class_instantiated_at_most)
            ],
            f,
            indent=4
        )

    # count functions that are used at most i times
    flat_function_call_counts = [
        count
        for callable_name, count in call_counts.items()
        if not callable_name.endswith("__init__")
    ]
    max_function_call_count = max(flat_function_call_counts)

    function_called_at_most = []
    for i in range(max_function_call_count + 1):
        function_called_at_most_i_times = len([count for count in flat_function_call_counts if count <= i])
        function_called_at_most.append(function_called_at_most_i_times)

    with out_dir.joinpath("$$$$$merged_function_called_at_most_index_times$$$$$.json").open("w") as f:
        json.dump(
            [
                {"maxCalls": index, "functionCount": count}
                for index, count in enumerate(function_called_at_most)
            ],
            f,
            indent=4
        )

    # count parameters where the most commonly used value is used in all but i cases
    flat_parameter_counts = [
        call_counts[callable_name] - max([count for count in parameters[parameter_name].values()],
                                         default=call_counts[callable_name])
        # otherwise the parameter is set but does not even exist
        if sum([count for count in parameters[parameter_name].values()]) == call_counts[callable_name]
        else sum([count for count in parameters[parameter_name].values()])

        for callable_name, parameters in value_counts.items()
        for parameter_name in parameters.keys()
    ]
    max_parameter_count = max(flat_parameter_counts)

    parameter_used_at_most = []
    for i in range(max_parameter_count + 1):
        parameter_used_at_most_i_times = len([count for count in flat_parameter_counts if count <= i])
        parameter_used_at_most.append(parameter_used_at_most_i_times)

    with out_dir.joinpath("$$$$$merged_parameter_used_at_most_index_times$$$$$.json").open("w") as f:
        json.dump(
            [{"maxUsages": index, "parameterCount": count} for index, count in enumerate(parameter_used_at_most)],
            f,
            indent=4
        )


def _is_relevant_qualified_name(qualified_name: str) -> bool:
    return any(qualified_name.startswith(prefix) for prefix in _relevant_packages)


def _is_relevant_python_file(source: str) -> bool:
    return any(prefix in source for prefix in _relevant_packages)


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
            self.parameters[qualified_name] = {}

        for parameter_name in bound_parameters.keys():
            if parameter_name not in self.parameters[qualified_name]:
                self.parameters[qualified_name][parameter_name] = []
            self.parameters[qualified_name][parameter_name].append(occurrence)

        # Count how often each value is used
        if qualified_name not in self.values:
            self.values[qualified_name] = {}

        for parameter_name, value in bound_parameters.items():
            stringified_value = _stringify_value(value)

            if parameter_name not in self.values[qualified_name]:
                self.values[qualified_name][parameter_name] = {}

            if stringified_value not in self.values[qualified_name][parameter_name]:
                self.values[qualified_name][parameter_name][stringified_value] = []

            self.values[qualified_name][parameter_name][stringified_value].append(occurrence)


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
) -> Optional[dict[str, astroid.NodeNG]]:
    # Improper call
    if parameters.args is None or arguments.has_invalid_arguments() or arguments.has_invalid_keywords():
        return None

    result: dict[str, astroid.NodeNG] = arguments.keyword_arguments.copy()

    positional_parameter_names = [it.name for it in (parameters.posonlyargs + parameters.args)][n_implicit_parameters:]

    for index, arg in enumerate(arguments.positional_arguments):
        if index >= len(positional_parameter_names):
            break

        result[positional_parameter_names[index]] = arg

    return result


def _stringify_value(value: astroid.NodeNG):
    return value.as_string()
