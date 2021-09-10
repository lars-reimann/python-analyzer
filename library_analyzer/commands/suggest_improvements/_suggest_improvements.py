import json
from io import TextIOWrapper
from pathlib import Path

from library_analyzer.commands.find_usages import UsageStore
from library_analyzer.commands.get_public_api import API


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


def remove_internal_usages(usages: UsageStore, public_api: API):
    for class_qname in list(usages.class_usages.keys()):
        if class_qname not in public_api.classes:
            print(f"Removing usages of internal class {class_qname}.")
            del usages.class_usages[class_qname]
