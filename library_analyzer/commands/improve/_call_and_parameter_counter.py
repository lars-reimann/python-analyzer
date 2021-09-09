import json
import multiprocessing
import sys
from pathlib import Path
from typing import Optional, Any

import astroid
from astroid.arguments import CallSite
from astroid.helpers import safe_infer

from library_analyzer.commands.get_public_api import get_public_api
from library_analyzer.utils import ASTWalker, list_files, initialize_and_read_exclude_file

# Type aliases
ClassName = str
CallableName = str
ParameterName = str
StringifiedValue = str
FileName = str
LineNumber = int
ColumnNumber = int
Occurrence = tuple[FileName, Optional[LineNumber], Optional[ColumnNumber]]
ClassStore = dict[ClassName, list[Occurrence]]
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

    lock = multiprocessing.Lock()
    with multiprocessing.Pool(processes=12, initializer=_initialize_process_environment, initargs=(lock,)) as pool:
        pool.starmap(
            _do_count_calls_and_parameters,
            [[it, exclude_file, out_dir] for it in python_files]
        )
    pool.join()

    (result_classes, result_calls, result_parameters, result_values) = _merge_results(out_dir)
    # _aggregate_results(out_dir, result_calls, result_parameters, result_values)
    _removed_classes(out_dir, result_classes)


def _initialize_process_environment(lock: multiprocessing.Lock):
    # noinspection PyGlobalUndefined
    global _lock
    _lock = lock


def _do_count_calls_and_parameters(
    python_file: str,
    exclude_file: Path,
    out_dir: Path,
):
    print(f"Working on {python_file}")

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


def _merge_results(out_dir: Path) -> tuple[ClassStore, CallStore, ParameterStore, ValueStore]:
    result_classes: ClassStore = {}
    result_calls: CallStore = {}
    result_parameters: ParameterStore = {}
    result_values: ValueStore = {}

    # Include all callables and parameters (and their default values) from relevant packages
    for package_name in _relevant_packages:
        callables, classes = get_public_api(package_name)

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

        for class_name in classes:
            result_classes[class_name] = []

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
                # not part of the public API
                continue

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

    # merge classes
    for class_name in result_classes.keys():
        for callable_name, occurrences in result_calls.items():
            if callable_name.startswith(class_name):
                result_classes[class_name].extend(occurrences)

    result_occurrences = {
        "classes": result_classes,
        "calls": result_calls,
        "parameters": result_parameters,
        "values": result_values
    }

    with out_dir.joinpath("$$$$$merged_occurrences$$$$$.json").open("w") as f:
        json.dump(result_occurrences, f, indent=4)

    return result_classes, result_calls, result_parameters, result_values


def _aggregate_results(out_dir: Path, result_calls: CallStore, result_parameters: ParameterStore,
                       result_values: ValueStore):
    call_counts, parameter_counts, value_counts = _count(out_dir, result_calls, result_parameters, result_values)
    _count_distribution(out_dir, call_counts, value_counts)
    _affected_occurrences(out_dir, result_calls, result_values, call_counts, value_counts)


def _removed_classes(out_dir: Path, class_store: ClassStore):
    all_public_classes = set(class_store.keys())

    used_public_classes: set[str] = set()
    for class_name, occurrences in class_store.items():
        if len(occurrences) > 0:
            used_public_classes.add(class_name)
    unused_public_classes = all_public_classes.difference(used_public_classes)

    with out_dir.joinpath("$$$$$merged_class_analysis$$$$$.json").open("w") as f:
        json.dump(
            {
                "all_public_classes": sorted(all_public_classes),
                "number_of_all_public_classes": len(all_public_classes),

                "used_public_classes": sorted(used_public_classes),
                "number_of_used_public_classes": len(used_public_classes),

                "unused_public_classes": sorted(unused_public_classes),
                "number_of_unused_public_classes": len(unused_public_classes),
            },
            f,
            indent=4
        )


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


def _affected_occurrences(
    out_dir: Path,
    result_calls: CallStore,
    result_values: ValueStore,
    call_counts: Any,
    value_counts: Any
) -> None:
    result = []

    for callable_call_cutoff in range(0, 101):
        for parameter_usage_cutoff in range(callable_call_cutoff, 101):
            removed_callables = _callables_called_at_most_n_times(call_counts, callable_call_cutoff)
            removed_parameters = _parameters_used_at_most_n_times(call_counts, value_counts, parameter_usage_cutoff)
            n_affected_files = _n_affected_files(result_calls, result_values, removed_callables, removed_parameters)
            result.append({
                "callCutoff": callable_call_cutoff,
                "parameterUsageCutoff": parameter_usage_cutoff,
                "affectedPrograms": n_affected_files
            })

    with out_dir.joinpath("$$$$$merged_affected_occurrences$$$$$.json").open("w") as f:
        json.dump(result, f, indent=4)


def _callables_called_at_most_n_times(call_counts: Any, n: int) -> list[CallableName]:
    return [
        callable_name
        for callable_name, count in call_counts.items()
        if count <= n
    ]


def _parameters_used_at_most_n_times(
    call_counts: Any,
    value_counts: Any,
    n: int
) -> list[tuple[CallableName, ParameterName, list[StringifiedValue]]]:
    return [
        (callable_name, parameter_name, [
            stringified_value
            for stringified_value in values.keys()
            if stringified_value != _most_common_value(value_counts, callable_name, parameter_name)[0]
        ])

        for callable_name, parameters in value_counts.items()
        for parameter_name, values in parameters.items()

        if _n_parameter_uses(call_counts, value_counts, callable_name, parameter_name) <= n
    ]


def _most_common_value(
    value_counts: Any,
    callable_name: str,
    parameter_name: str
) -> tuple[Optional[StringifiedValue], int]:
    values = value_counts[callable_name][parameter_name].items()

    result = None, 0
    for stringified_value, count in values:
        if count > result[1]:
            result = stringified_value, count

    return result


def _n_parameter_uses(call_counts: Any, value_counts: Any, callable_name: str, parameter_name: str) -> int:
    n_calls = call_counts[callable_name]
    n_parameters_set = sum(count for count in value_counts[callable_name][parameter_name].values())

    if n_calls == n_parameters_set:  # sum of counts how often each value is used should equal the number of calls
        most_common_value, count = _most_common_value(value_counts, callable_name, parameter_name)
        if most_common_value is None:
            return 0

        return n_calls - count

    else:  # otherwise the parameter is set but does not even exist
        return n_parameters_set


def _n_affected_files(
    result_calls: CallStore,
    result_values: ValueStore,
    removed_callables: list[CallableName],
    removed_parameters: list[tuple[CallableName, ParameterName, list[StringifiedValue]]]
) -> int:
    affected_files = set()

    for callable_name in removed_callables:
        for occurrence in result_calls[callable_name]:
            affected_files.add(occurrence[0])

    for callable_name, parameter_name, stringified_values in removed_parameters:
        for stringified_value in stringified_values:
            # if the stringified value is not listed then it's never used explicitly (can only happen when
            # another value is used more often than the default)
            for occurrence in (result_values[callable_name][parameter_name]["values"].get(stringified_value) or []):
                affected_files.add(occurrence[0])

    return len(affected_files)


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

    new_is_from_object = new and new.parent.scope().qname == "object"
    new_is_from_builtins = new and new.root().qname in sys.builtin_module_names

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
