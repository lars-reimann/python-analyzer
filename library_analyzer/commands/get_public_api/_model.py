from __future__ import annotations

from typing import Any, Optional


class API:

    @staticmethod
    def from_json(json: Any) -> API:
        result = API(
            json["distribution"],
            json["package"],
            json["version"]
        )

        for class_qname in json["classes"]:
            result.add_class(class_qname)

        for function_json in json["functions"]:
            result.add_function(Function.from_json(function_json))

        return result

    def __init__(self, distribution: str, package: str, version: str) -> None:
        self.distribution: str = distribution
        self.package: str = package
        self.version: str = version
        self.classes: set[str] = set()
        self.functions: dict[str, Function] = dict()

    def add_class(self, qname: str) -> None:
        self.classes.add(qname)

    def add_function(self, function: Function) -> None:
        self.functions[function.qname] = function

    def to_json(self) -> Any:
        return {
            "distribution": self.distribution,
            "package": self.package,
            "version": self.version,
            "classes": sorted(list(self.classes)),
            "functions": [
                function.to_json()
                for function in sorted(self.functions.values(), key=lambda it: it.qname)
            ]
        }

class Function:

    @staticmethod
    def from_json(json: Any) -> Function:
        return Function(
            json["qname"],
            [Parameter.from_json(parameter_json) for parameter_json in json["parameters"]]
        )

    def __init__(self, qname: str, parameters: list[Parameter]) -> None:
        self.qname: str = qname
        self.parameters: list[Parameter] = parameters

    def to_json(self) -> Any:
        return {
            "qname": self.qname,
            "parameters": [
                parameter.to_json()
                for parameter in self.parameters
            ]
        }

class Parameter:

    @staticmethod
    def from_json(json: Any) -> Parameter:
        return Parameter(
            json["name"],
            json["default_value"]
        )

    def __init__(self, name: str, default_value: Optional[str]):
        self.name: str = name
        self.default_value: Optional[str] = default_value

    def to_json(self) -> Any:
        return {
            "name": self.name,
            "default_value": self.default_value
        }

