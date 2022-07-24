from abc import abstractmethod
import boto3
from boto3.dynamodb.conditions import Attr, Key
from datetime import datetime, timezone
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

    def bind_partial(self, key_variables):
        format_chunks = self.format_str.split('#')
        chunks = []
        full_bound = False

        for idx, chunk in enumerate(format_chunks):
            is_last_chunk = idx == len(format_chunks) - 1
            variable_chunk = re.match(r'\{.*\}', chunk)

            if not variable_chunk:
                chunks.append(chunk)
                if is_last_chunk:
                    full_bound = True

                continue

            print(variable_chunk.group(0))
            variable_name = variable_chunk.group(0)[1:-1]

            if variable_name not in key_variables:
                break

            chunks.append(chunk.format(**key_variables))

            if is_last_chunk:
                full_bound = True

        key_str1 = '#'.join(chunks)
        key_str2 = key_str1 if full_bound else f'{key_str1}#'

        return key_str2


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

    @classmethod
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

        # 'ClassName' and 'LastUpdate'
        item['ClassName'] = self.__class__.__name__
        item['LastUpdate'] = self.last_update

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
            **{camel_to_snake(k): v for k, v in item.items()},
            **key_variables,
        })

    @classmethod
    def from_dict(cls, dict):
        instance = cls()
        
        for attr_name in cls.attributes:
            setattr(instance, attr_name, dict[attr_name])

        for attr_name in cls._key_variable_names:
            setattr(instance, attr_name, dict[attr_name])

        return instance


class CRUDInterface:
    # abstract methods
    @classmethod
    @abstractmethod
    def get_table(cls):
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def from_dict(cls, dict):
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def _execute_query(cls, query_params):
        raise NotImplementedError()

    # class methods
    @classmethod
    def find_by_key(cls, **kwargs):
        items = cls._execute_query({
            'KeyConditionExpression': Key('PK').eq(cls.pk.make_key_str(kwargs)) & Key('SK').eq(cls.sk.make_key_str(kwargs))
        })

        if not items:
            return None

        return cls.from_item(items[0])

    @classmethod
    def find_by_key_prefix(cls, **kwargs):
        print(cls.sk.bind_partial(kwargs))
        items = cls._execute_query({
            'KeyConditionExpression': Key('PK').eq(cls.pk.make_key_str(kwargs)) & Key('SK').begins_with(cls.sk.bind_partial(kwargs))
        })

        return [cls.from_item(item) for item in items]

    @classmethod
    def create(cls, **kwargs):
        new_instance = cls.from_dict(kwargs)
        setattr(new_instance, 'last_update', datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z'))

        item = new_instance.to_item()

        # Save to DynamoDB
        table = cls.get_table()
        table.put_item(
            Item=item
        )

        return new_instance

    @classmethod
    def create_if_no_conflict(cls, **kwargs):
        new_instance = cls.from_dict(kwargs)
        setattr(new_instance, 'last_update', datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z'))

        item = new_instance.to_item()

        # Save to DynamoDB
        table = cls.get_table()
        table.put_item(
            Item=item,
            Expected={
                'PK': {
                    'Exists': False
                },
                'SK': {
                    'Exists': False
                },
            }
        )

        return new_instance

    @classmethod
    def delete_by_key(cls, **kwargs):
        raise NotImplementedError()

    # instance methods
    def save(self):
        self.last_update = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z')

        # Save to DynamoDB
        table = self.get_table()
        table.put_item(
            Item=self.to_item()
        )

    def save_if_no_conflict(self, last_update=None):
        prev_timestamp = last_update if last_update else self.last_update
        self.last_update = datetime.now(tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f%z')

        # Save to DynamoDB
        table = self.get_table()
        table.put_item(
            Item=self.to_item(),
            Expected={
                'LastUpdate': {
                    'Value': prev_timestamp
                }
            }
        )


class QueryInterface:
    @classmethod
    @abstractmethod
    def get_table(cls):
        ...

    @classmethod
    def _execute_query(cls, query_params):
        result = cls.get_table().query(**query_params)
        items = result.get('Items', [])

        while result.get('LastEvaluatedKey'):
            result = cls.get_table().query(**{
                **query_params,
                **{
                    'LastEvaluatedKey': result['LastEvaluatedKey']
                }
            })

            items += result.get('Items', [])

        return items

    @classmethod
    def _all_subclasses(cls):
        return set(cls.__subclasses__()).union(
            [s for c in cls.__subclasses__() for s in c._all_subclasses()])

    @classmethod
    def _get_entity_classes(cls):
        return {
            clazz.__name__: clazz
            for clazz in cls._all_subclasses()
            if hasattr(clazz, 'pk') and hasattr(clazz, 'sk') and hasattr(clazz, 'attributes')
        }


    @classmethod
    def multiple_entity_query(cls, *, pk, sk=None, sk_prefix=None, index=None):
        if sk and sk_prefix:
            raise Exception()

        query_params = {}

        pk_condition = Key('GSI1PK' if index else 'PK').eq(pk)

        if not sk and not sk_prefix:
            query_params["KeyConditionExpression"] = pk_condition
        else:
            if sk:
                sk_condition = Key('GSI1SK' if index else 'SK').eq(sk)
            elif sk_prefix:
                sk_condition = Key('GSI1SK' if index else 'SK').begins_with(sk_prefix)

            query_params["KeyConditionExpression"] = pk_condition & sk_condition

        if index:
            query_params['IndexName'] = index

        items = cls._execute_query(query_params)

        # Instantiate entities
        entity_classes = cls._get_entity_classes()

        entity_dict = {}

        for item in items:
            entity_type = item['ClassName']
            entity_class = entity_classes[entity_type]

            entities = entity_dict.get(entity_type, [])
            entity_dict[entity_type] = entities + [ entity_class.from_item(item) ]

        return entity_dict
