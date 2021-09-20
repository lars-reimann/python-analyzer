import json
from io import TextIOWrapper
from pathlib import Path

from library_analyzer.commands.find_usages import UsageStore, Usage
from library_analyzer.commands.get_api import API
from library_analyzer.utils import parent_qname


def suggest_improvements(
    api_file: TextIOWrapper,
    usages_file: TextIOWrapper,
    out_dir: Path,
    min_usages: int
):
    with api_file:
        api_json = json.load(api_file)
        api = API.from_json(api_json)

    with usages_file:
        usages_json = json.load(usages_file)
        usages = UsageStore.from_json(usages_json)

    out_dir.mkdir(parents=True, exist_ok=True)
    base_file_name = api_file.name.replace("__api.json", "")

    __preprocess_usages(usages, api)
    __create_usage_distributions(usages, out_dir, base_file_name)
    __remove_rarely_used_api_elements(usages, min_usages, out_dir, base_file_name)
    __optional_vs_required_parameters(usages, api, out_dir, base_file_name)


def __preprocess_usages(usages: UsageStore, api: API) -> None:
    __remove_internal_usages(usages, api)
    __add_unused_api_elements(usages, api)
    __add_implicit_usages_of_default_value(usages, api)


def __create_usage_distributions(usages: UsageStore, out_dir: Path, base_file_name: str) -> None:
    class_usage_distribution = __create_class_or_function_usage_distribution(usages.class_usages)
    with out_dir.joinpath(f"{base_file_name}__class_usage_distribution.json").open("w") as f:
        json.dump(class_usage_distribution, f, indent=2)

    function_usage_distribution = __create_class_or_function_usage_distribution(usages.function_usages)
    with out_dir.joinpath(f"{base_file_name}__function_usage_distribution.json").open("w") as f:
        json.dump(function_usage_distribution, f, indent=2)

    parameter_usage_distribution = __create_parameter_usage_distribution(usages.parameter_usages, usages.value_usages)
    with out_dir.joinpath(f"{base_file_name}__parameter_usage_distribution.json").open("w") as f:
        json.dump(parameter_usage_distribution, f, indent=2)


def __remove_internal_usages(usages: UsageStore, api: API) -> None:
    """
    Removes usages of internal parts of the API. It might incorrectly remove some calls to methods that are inherited
    from internal classes into a public class but these are just fit/predict/etc., i.e. something we want to keep
    unchanged anyway.

    :param usages: Usage store
    :param api: Description of the API
    """

    # Internal classes
    for class_qname in list(usages.class_usages.keys()):
        if not api.is_public_class(class_qname):
            print(f"Removing usages of internal class {class_qname}")
            usages.remove_class(class_qname)

    # Internal functions
    for function_qname in list(usages.function_usages.keys()):
        if not api.is_public_function(function_qname):
            print(f"Removing usages of internal function {function_qname}")
            usages.remove_function(function_qname)

    # Internal parameters
    for parameter_qname in list(usages.parameter_usages.keys()):
        function_qname = parent_qname(parameter_qname)
        if not api.is_public_function(function_qname):
            print(f"Removing usages of internal parameter {parameter_qname}")
            usages.remove_parameter(parameter_qname)


def __add_unused_api_elements(usages: UsageStore, api: API) -> None:
    # Public classes
    for class_qname in api.classes:
        if api.is_public_class(class_qname):
            usages.init_class(class_qname)

    # Public functions
    for function in api.functions.values():
        if api.is_public_function(function.qname):
            usages.init_function(function.qname)

            # "Public" parameters
            for parameter in function.parameters:
                parameter_qname = f"{function.qname}.{parameter.name}"
                usages.init_parameter(parameter_qname)
                usages.init_value(parameter_qname)


def __add_implicit_usages_of_default_value(usages: UsageStore, api: API) -> None:
    for parameter_qname, parameter_usage_list in list(usages.parameter_usages.items()):
        default_value = api.get_default_value(parameter_qname)
        function_qname = parent_qname(parameter_qname)
        function_usage_list = usages.function_usages[function_qname]

        locations_of_implicit_usages_of_default_value = set(
            [it.location for it in function_usage_list]
        ) - set(
            [it.location for it in parameter_usage_list]
        )

        for location in locations_of_implicit_usages_of_default_value:
            usages.add_parameter_usage(parameter_qname, location)
            usages.add_value_usage(parameter_qname, default_value, location)


def __create_class_or_function_usage_distribution(usages: dict[str, list[Usage]]) -> dict[int, int]:
    """
    Creates a dictionary X -> N where N indicates the number of classes/functions that are used at most X times.

    :param usages: Usages of classes/functions.
    :return: The usage distribution.
    """

    result = {}

    max_usages = max(len(it) for it in usages.values())
    for i in range(max_usages + 1):
        result[i] = len([it for it in usages.values() if len(it) <= i])

    return result


def __create_parameter_usage_distribution(
    parameter_usages: dict[str, list[Usage]],
    value_usages: dict[str, dict[str, list[Usage]]]
) -> dict[int, int]:
    """
    Creates a dictionary X -> N where N indicates the number of parameters that are set at most X times to a value other
    than the most commonly used value (which might differ from the default value).

    :param parameter_usages: Usages of parameters.
    :param value_usages: Values assigned to parameters.
    :return: The usage distribution.
    """

    result = {}

    max_usages = max(
        __n_not_set_to_most_common_value(it, parameter_usages, value_usages)
        for it in parameter_usages.keys()
    )

    for i in range(max_usages + 1):
        result[i] = len(
            [
                it
                for it in parameter_usages.keys()
                if __n_not_set_to_most_common_value(it, parameter_usages, value_usages) <= i
            ]
        )

    return result


def __n_not_set_to_most_common_value(
    parameter_qname: str,
    parameter_usages: dict[str, list[Usage]],
    value_usages: dict[str, dict[str, list[Usage]]]
) -> int:
    """Counts how often a parameter is set to a value other than the most commonly used value."""

    n_total_usage = len(parameter_usages[parameter_qname])

    # Parameter is unused
    # Checking both conditions even though one implies the other to ensure correctness of the program
    if n_total_usage == 0 and len(value_usages[parameter_qname].values()) == 0:
        return 0

    n_set_to_most_commonly_used_value = max(len(it) for it in value_usages[parameter_qname].values())

    return n_total_usage - n_set_to_most_commonly_used_value


def __remove_rarely_used_api_elements(
    usages: UsageStore,
    min_usages: int,
    out_dir: Path,
    base_file_name: str
) -> None:
    rarely_used_classes = __remove_rarely_used_classes(usages, min_usages)
    with out_dir.joinpath(f"{base_file_name}__classes_used_fewer_than_{min_usages}_times.json").open("w") as f:
        json.dump(rarely_used_classes, f, indent=2)

    rarely_used_functions = __remove_rarely_used_functions(usages, min_usages)
    with out_dir.joinpath(f"{base_file_name}__functions_used_fewer_than_{min_usages}_times.json").open("w") as f:
        json.dump(rarely_used_functions, f, indent=2)

    rarely_used_parameters = __remove_rarely_used_parameters(usages, min_usages)
    with out_dir.joinpath(f"{base_file_name}__parameters_used_fewer_than_{min_usages}_times.json").open("w") as f:
        json.dump(rarely_used_parameters, f, indent=2)


def __remove_rarely_used_classes(usages: UsageStore, min_usages: int) -> list[str]:
    result = []

    for class_qname in list(usages.class_usages.keys()):
        if usages.n_class_usages(class_qname) < min_usages:
            result.append(class_qname)
            usages.remove_class(class_qname)

    return sorted(result)


def __remove_rarely_used_functions(usages: UsageStore, min_usages: int) -> list[str]:
    result = []

    for function_qname in list(usages.function_usages.keys()):
        if usages.n_function_usages(function_qname) < min_usages:
            result.append(function_qname)
            usages.remove_function(function_qname)

    return sorted(result)


def __remove_rarely_used_parameters(usages: UsageStore, min_usages: int) -> list[str]:
    result = []

    for parameter_qname in list(usages.parameter_usages.keys()):
        usage_count = __n_not_set_to_most_common_value(parameter_qname, usages.parameter_usages, usages.value_usages)

        if usage_count < min_usages:
            result.append(parameter_qname)
            usages.remove_parameter(parameter_qname)

    return sorted(result)


def __optional_vs_required_parameters(
    usages: UsageStore,
    public_api: API,
    out_dir: Path,
    base_file_name: str
) -> None:
    # TODO: Determine whether parameter should be constant (already removed)/required/optional based on entropy
    # TODO: Use must commonly set value as default

    pass
