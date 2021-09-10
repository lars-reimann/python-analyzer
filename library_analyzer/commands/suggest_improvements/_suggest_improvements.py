import json
from io import TextIOWrapper
from pathlib import Path

from library_analyzer.commands.find_usages import UsageStore
from library_analyzer.commands.get_public_api import API
from library_analyzer.utils import parent_qname


def suggest_improvements(
    api_file: TextIOWrapper,
    usages_file: TextIOWrapper,
    out_dir: Path,
    min_usages: int
):
    with api_file:
        api_json = json.load(api_file)
        public_api = API.from_json(api_json)

    with usages_file:
        usages_json = json.load(usages_file)
        usages = UsageStore.from_json(usages_json)

    remove_internal_usages(usages, public_api)
    add_unused_api_elements(usages, public_api)
    add_implicit_usages_of_default_value(usages, public_api)

    print(len(public_api.classes))
    print(len(usages.value_usages))


def remove_internal_usages(usages: UsageStore, public_api: API) -> None:
    """
    Removes usages of internal parts of the API. It might incorrectly remove some calls to methods that are inherited
    from internal classes into a public class but these are just fit/predict/etc., i.e. something we want to keep
    unchanged anyway.

    :param usages: Usage store
    :param public_api: Description of the public API
    """

    # Internal classes
    for class_qname in list(usages.class_usages.keys()):
        if class_qname not in public_api.classes:
            print(f"Removing usages of internal class {class_qname}")
            usages.remove_class(class_qname)

    # Internal functions
    for function_qname in list(usages.function_usages.keys()):
        if function_qname not in public_api.functions:
            print(f"Removing usages of internal function {function_qname}")
            usages.remove_function(function_qname)

    # Internal parameters
    for parameter_qname in list(usages.parameter_usages.keys()):
        function_qname = parent_qname(parameter_qname)
        if function_qname not in public_api.functions:
            print(f"Removing usages of internal parameter {parameter_qname}")
            usages.remove_parameter(parameter_qname)
            usages.remove_value(parameter_qname)


def add_unused_api_elements(usages: UsageStore, public_api: API) -> None:
    # Public classes
    for class_qname in public_api.classes:
        usages.init_class(class_qname)

    # Public functions
    for function in public_api.functions.values():
        usages.init_function(function.qname)

        # "Public" parameters
        for parameter in function.parameters:
            parameter_qname = f"{function.qname}.{parameter.name}"
            usages.init_parameter(parameter_qname)
            usages.init_value(parameter_qname)


def add_implicit_usages_of_default_value(usages: UsageStore, public_api: API) -> None:
    for parameter_qname, parameter_usage_list in list(usages.parameter_usages.items()):
        default_value = public_api.get_default_value(parameter_qname)
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
