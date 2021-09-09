from __future__ import annotations

from typing import Any, Optional


class API:
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
    def __init__(self, name: str, parameters: list[Parameter]) -> None:
        self.qname: str = name
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
    def __init__(self, name: str, default_value: Optional[str]):
        self.name: str = name
        self.default_value: Optional[str] = default_value

    def to_json(self) -> Any:
        return {
            "name": self.name,
            "default_value": self.default_value
        }

