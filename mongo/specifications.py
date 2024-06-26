import re
from typing import Any


class Specification:
    def to_query(self) -> dict[str, Any]:
        raise NotImplementedError("Subclasses must implement `to_query` method")


class DecimalRangeParameter(Specification):
    def __init__(self, param_name: str, val_from: int = None, val_to: int = None):
        self.val_from = val_from
        self.val_to = val_to
        self.param_name = param_name

    def to_query(self) -> dict[str, Any]:
        if not self.val_from and not self.val_to:
            raise ValueError
        query = {self.param_name: {}}
        if self.val_from is not None:
            query[self.param_name]['$gte'] = int(self.val_from)
        if self.val_to is not None:
            query[self.param_name]['$lte'] = int(self.val_to)
        return query


class SimpleParameter(Specification):
    def __init__(self, param_name: str, value: Any):
        self.param_name = param_name
        self.value = value

    def to_query(self) -> dict[str, Any]:
        if not self.value:
            raise ValueError
        query = {self.param_name: self.value}
        return query


class OneOfParameter(Specification):
    def __init__(self, param_name: str, values: list):
        self.param_name = param_name
        self.values = values

    def to_query(self) -> dict[str, Any]:
        if not self.values:
            raise ValueError
        query = {self.param_name: {"$in": self.values}}
        return query


class SubSetParameter(Specification):
    def __init__(self, param_name: str, values: list):
        self.param_name = param_name
        self.values = values

    def to_query(self) -> dict[str, Any]:
        if not self.values:
            raise ValueError
        query = {self.param_name: {"$all": self.values}}
        return query


class MakeParameter(Specification):
    def __init__(self, makes_to_include: dict[str, list[str]] = None, makes_to_exclude: dict[str, list[str]] = None):
        if not makes_to_include:
            makes_to_include = {}
        if not makes_to_exclude:
            makes_to_exclude = {}
        self.makes_to_include = makes_to_include
        self.makes_to_exclude = makes_to_exclude

    @staticmethod
    def normalize_string(str_value: str) -> str:
        """Unification of naming standard for Make and Model fields"""
        return ' '.join(str.capitalize(a) for a in re.split('[- ]', str_value))

    def to_query(self) -> dict[str, Any]:
        or_clauses = []

        # Include logic
        for make, models in self.makes_to_include.items():
            if not make:
                continue
            make = self.normalize_string(make)
            if models:  # If models are specified, include both make and models
                make = self.normalize_string(make)
                models = [self.normalize_string(model) for model in models]
                or_clauses.append({
                    '$and': [
                        {'make': make},
                        {'model': {'$in': models}}
                    ]
                })
            else:  # If no models, include just the make
                or_clauses.append({'make': self.normalize_string(make)})

        # Exclude logic
        and_clauses = []
        for make, models in self.makes_to_exclude.items():
            if models:  # If models are specified, exclude both make and models
                make = self.normalize_string(make)
                models = [self.normalize_string(model) for model in models]
                and_clauses.append({
                    '$and': [
                        {'make': {'$ne': make}},
                        {'model': {'$nin': models}}
                    ]
                })
            else:  # If no models, exclude just the make
                and_clauses.append({'make': {'$ne': self.normalize_string(make)}})

        query = {}

        # Combine both inclusive and exclusive clauses
        if or_clauses:
            query['$or'] = or_clauses

        if and_clauses:
            query['$and'] = and_clauses

        return query
