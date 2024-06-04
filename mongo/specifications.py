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
    def __init__(self, makes: dict[str, list[str]]):
        self.makes = makes

    @staticmethod
    def normalize_string(str_value: str):
        res = ' '.join(str.capitalize(a) for a in str_value.split('-'))
        return res

    def to_query(self) -> dict[str, Any]:
        if not self.makes or not [key for key in self.makes.keys() if key is not None]:
            raise ValueError
        or_clauses = []
        for make, models in self.makes.items():
            if not make:
                continue
            make = self.normalize_string(make)
            if models:
                models = [self.normalize_string(model) for model in models]
                or_clauses.append({
                    '$and': [
                        {'make': make},
                        {'model': {'$in': models}}
                    ]
                })
            else:
                or_clauses.append({'make': make})
        return {'$or': or_clauses}
