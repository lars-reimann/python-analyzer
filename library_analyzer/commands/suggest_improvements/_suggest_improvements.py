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
            del usages.class_usages[class_qname]

    # Internal functions
    for function_qname in list(usages.function_usages.keys()):
        if function_qname not in public_api.functions:
            print(f"Removing usages of internal function {function_qname}")
            del usages.function_usages[function_qname]

    # Internal parameters
    for parameter_qname in list(usages.parameter_usages.keys()):
        function_qname = parent_qname(parameter_qname)
        if function_qname not in public_api.functions:
            print(f"Removing usages of internal parameter {parameter_qname}")
            del usages.parameter_usages[parameter_qname]
            del usages.value_usages[parameter_qname]
