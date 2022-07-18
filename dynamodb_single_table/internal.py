from abc import abstractmethod
import boto3
from datetime import datetime
import re


def camel_to_snake(name):
    name = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def snake_to_camel(name):
    return ''.join(word.title() for word in name.split('_'))


class KeyFormat:
    # FIXME: Can't extract variable if they are inside a chunk like 'race-{race_id}#part-{part_id}'.

    def __init__(self, format_str):
        self.format_str = format_str

    @property
    def variable_names(self):
        return [
            chunk[1:-1] for chunk in self.format_str.split('#')
            if re.match(r'^\{.*\}$', chunk)
        ]

    def extract_variables(self, key_str):
        chunks = zip(self.format_str.split('#'), key_str.split('#'))
        return {f[1:-1]: k for (f, k) in chunks if re.match(r'\{.*\}]', f)}

    def make_key_str(self, key_variables):
        return self.format_str.format(**key_variables)


class ObjectItemConvertion:
    @classmethod
    @property
    @abstractmethod
    def pk(cls):
        ...

    @classmethod
    @property
    @abstractmethod
    def sk(cls):
        ...

    @classmethod
    @property
    @abstractmethod
    def attributes(cls):
        ...

    @property
    def _key_variable_names(cls):
        key_variable_names = set(sum([
            cls.pk.variable_names,
            cls.sk.variable_names,
        ], []))

        if hasattr(cls, 'gsi1_pk'):
            key_variable_names = key_variable_names | set(cls.gsi1_pk.variable_names)

        if hasattr(cls, 'gsi1_sk'):
            key_variable_names = key_variable_names | set(cls.gsi1_sk.variable_names)

        return key_variable_names

    @property
    def _key_variables(self):
        return {variable_name: getattr(self, variable_name) for variable_name in self._key_variable_names}

    def to_item(self):
        item = {}

        # Set PK and SK
        item['PK'] = self.pk.make_key_str(self._key_variables)
        item['SK'] = self.sk.make_key_str(self._key_variables)

        # Set GS1PK and GSI1SK
        if hasattr(self, 'gsi1_pk'):
            item['GSI1PK'] = self.gsi1_pk.make_key_str(self._key_variables)

        if hasattr(self, 'gsi1_pk'):
            item['GSI1SK'] = self.gsi1_sk.make_key_str(self._key_variables)

        # Set non key attributes
        # Set attributes
        for attr_name in self.attributes:
            item[snake_to_camel(attr_name)] = getattr(self, attr_name)

        # TODO: 'Type' and 'LastUpdate'
        item['ClassName'] = self.__class__.__name__

        return item

    @classmethod
    def from_item(cls, item):
        if item['ClassName'] != cls.__name__:
            raise RuntimeError(f'Unknown class name (%s)' % (item['ClassName'],))

        key_variables = {}

        # Set key attributes
        key_variables.update(cls.pk.extract_variables(item['PK']))
        key_variables.update(cls.pk.extract_variables(item['SK']))

        # Set gsi1 key attributes
        if hasattr(cls, 'gsi1_pk'):
            key_variables.update(cls.gsi1_pk.extract_variables(item['GSI1PK']))

        if hasattr(cls, 'gsi1_sk'):
            key_variables.update(cls.gsi1_sk.extract_variables(item['GSI1SK']))

        return cls.from_dict({
            **item.copy(),
            **key_variables,
        })

    @classmethod
    def from_dict(cls, dict):
        instance = cls()

        for k, v in dict.items():
            # TODO: Check attribute name are valid.
            setattr(instance, k, v)

        return instance


class CRUDInterface:
    # abstract methods
    @classmethod
    @abstractmethod
    def get_table(cls):
        ...

    @classmethod
    @abstractmethod
    def from_dict(cls, dict):
        ...

    # class methods
    @classmethod
    def find_by_key(cls, **kwargs):
        raise NotImplementedError()

    @classmethod
    def search_by_key(cls, **kwargs):
        raise NotImplementedError()

    @classmethod
    def create(cls, **kwargs):
        new_instance = cls.from_dict(kwargs)
        setattr(new_instance, 'last_update', datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%f%z'))

        # Save to DynamoDB
        table = cls.get_table()
        table.put_item(
            Item=new_instance.to_item()
        )

        return new_instance

    @classmethod
    def create_if_no_conflict(self, **kwargs):
        raise NotImplementedError()

    @classmethod
    def delete_by_key(cls, **kwargs):
        ...

    # instance methods
    def save(self):
        ...

    def save_if_no_conflict(self, last_update):
        raise NotImplementedError()


class QueryInterface:
    @classmethod
    @abstractmethod
    def get_table(cls):
        ...

    @classmethod
    def multiple_entity_query(cls, **kwargs):
        result = cls.get_table().query(**kwargs)
        items = result.get('Items', [])

        while result['LastEvaluatedKey']:
            result = cls.get_table().query(**{
                **kwargs,
                **{
                    'LastEvaluatedKey': result['LastEvaluatedKey']
                }
            })

            items += result.get('Items', [])

        # TODO: Instantiate entities
