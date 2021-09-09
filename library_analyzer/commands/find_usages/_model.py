from __future__ import annotations

from typing import Any, Optional

ClassQName = str
FunctionQName = str
ParameterQName = str
StringifiedValue = str


class UsageStore:

    @staticmethod
    def from_json(json: Any) -> UsageStore:
        result = UsageStore()

        # Revive class usages
        class_usages = json["class_usages"]
        for qname, locations in class_usages.items():
            for location in locations:
                result.add_class_usage(qname, Location.from_json(location))

        # Revive function usages
        function_usages = json["function_usages"]
        for qname, locations in function_usages.items():
            for location in locations:
                result.add_function_usage(qname, Location.from_json(location))

        # Revive parameter usages
        parameter_usages = json["parameter_usages"]
        for qname, locations in parameter_usages.items():
            for location in locations:
                result.add_parameter_usage(qname, Location.from_json(location))

        # Revive value usages
        value_usages = json["value_usages"]
        for parameter_qname, values in value_usages.items():
            for value, locations in values.items():
                for location in locations:
                    result.add_value_usage(parameter_qname, value, Location.from_json(location))

        return result

    def __init__(self) -> None:
        self.class_usages: dict[ClassQName, list[ClassUsage]] = {}
        self.function_usages: dict[FunctionQName, list[FunctionUsage]] = {}
        self.parameter_usages: dict[ParameterQName, list[ParameterUsage]] = {}
        self.value_usages: dict[ParameterQName, dict[StringifiedValue, list[ValueUsage]]] = {}

    def add_class_usage(self, qname: ClassQName, location: Location) -> None:
        if qname not in self.class_usages:
            self.class_usages[qname] = []

        self.class_usages[qname].append(ClassUsage(qname, location))

    def add_function_usage(self, qname: FunctionQName, location: Location) -> None:
        if qname not in self.function_usages:
            self.function_usages[qname] = []

        self.function_usages[qname].append(FunctionUsage(qname, location))

    def add_parameter_usage(self, qname: ParameterQName, location: Location) -> None:
        if qname not in self.parameter_usages:
            self.parameter_usages[qname] = []

        self.parameter_usages[qname].append(ParameterUsage(qname, location))

    def add_value_usage(self, parameter_qname: ParameterQName, value: StringifiedValue, location: Location) -> None:
        if parameter_qname not in self.value_usages:
            self.value_usages[parameter_qname] = {}

        if value not in self.value_usages[parameter_qname]:
            self.value_usages[parameter_qname][value] = []

        self.value_usages[parameter_qname][value].append(ValueUsage(parameter_qname, value, location))

    def merge_other_into_self(self, other_usage_store: UsageStore) -> UsageStore:
        """
        Merges the other usage store into this one **in-place** and returns this store.

        :param other_usage_store: The usage store to merge into this one.
        :return: This usage store.
        """

        # Merge class usages
        for usages in other_usage_store.class_usages.values():
            for usage in usages:
                self.add_class_usage(usage.qname, usage.location)

        # Merge function usages
        for usages in other_usage_store.function_usages.values():
            for usage in usages:
                self.add_function_usage(usage.qname, usage.location)

        # Merge parameter usages
        for usages in other_usage_store.parameter_usages.values():
            for usage in usages:
                self.add_parameter_usage(usage.qname, usage.location)

        # Merge value usages
        for values in other_usage_store.value_usages.values():
            for usages in values.values():
                for usage in usages:
                    self.add_value_usage(usage.parameter_qname, usage.value, usage.location)

        return self

    def to_json(self) -> Any:
        return {
            "class_usages": {
                qname: [
                    usage.location.to_json()
                    for usage in usages
                ]
                for qname, usages in self.class_usages.items()
            },
            "function_usages": {
                qname: [
                    usage.location.to_json()
                    for usage in usages
                ]
                for qname, usages in self.function_usages.items()
            },
            "parameter_usages": {
                qname: [
                    usage.location.to_json()
                    for usage in usages
                ]
                for qname, usages in self.parameter_usages.items()
            },
            "value_usages": {
                parameter_qname: {
                    value: [
                        usage.location.to_json()
                        for usage in usages
                    ]
                    for value, usages in values.items()
                }
                for parameter_qname, values in self.value_usages.items()
            },
        }


class ClassUsage:
    def __init__(self, qname: ClassQName, location: Location) -> None:
        self.qname: ClassQName = qname
        self.location: Location = location

    def to_json(self) -> Any:
        return {
            "qname": self.qname,
            "location": self.location.to_json()
        }


class FunctionUsage:
    def __init__(self, qname: FunctionQName, location: Location) -> None:
        self.qname: FunctionQName = qname
        self.location: Location = location

    def to_json(self) -> Any:
        return {
            "qname": self.qname,
            "location": self.location.to_json()
        }


class ParameterUsage:
    def __init__(self, qname: ParameterQName, location: Location) -> None:
        self.qname: ParameterQName = qname
        self.location: Location = location

    def to_json(self) -> Any:
        return {
            "qname": self.qname,
            "location": self.location.to_json()
        }


class ValueUsage:
    def __init__(self, parameter_qname: ParameterQName, value: StringifiedValue, location: Location) -> None:
        self.parameter_qname: ParameterQName = parameter_qname
        self.value: StringifiedValue = value
        self.location: Location = location

    def to_json(self) -> Any:
        return {
            "parameter_qname": self.parameter_qname,
            "value": self.value,
            "location": self.location.to_json()
        }


FileName = str
LineNumber = int
ColumnNumber = int


class Location:

    @staticmethod
    def from_json(json: Any) -> Location:
        return Location(
            json["file"],
            json["line"],
            json["column"]
        )

    def __init__(self, file: FileName, line: Optional[LineNumber], column: Optional[ColumnNumber]) -> None:
        self.file: FileName = file
        self.line: Optional[LineNumber] = line
        self.column: Optional[ColumnNumber] = column

    def to_json(self) -> Any:
        return {
            "file": self.file,
            "line": self.line,
            "column": self.column
        }
