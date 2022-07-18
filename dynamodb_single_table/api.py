from abc import abstractmethod
import boto3

from .internal import KeyFormat, ObjectItemConvertion, CRUDInterface, QueryInterface


class PK(KeyFormat):
    ...


class SK(KeyFormat):
    ...


class Entity(ObjectItemConvertion, CRUDInterface):
    @classmethod
    @abstractmethod
    def get_table(cls):
        ...

    @classmethod
    @property
    @abstractmethod
    def pk(cld):
        ...

    @classmethod
    @property
    @abstractmethod
    def sk(cls):
        ...

    @classmethod
    @property
    @abstractmethod
    def attributes(cld):
        ...


class BaseTableHolder:
    @classmethod
    def get_table(cls):
        return cls._table


def create_table_holder(table_name):
    table = boto3.resource('dynamodb').Table(table_name)

    new_class = type(f"TableHolderFor{table_name}", (BaseTableHolder, QueryInterface,), {
        "__init__": lambda self: None,
    })

    new_class._table = table

    return new_class
