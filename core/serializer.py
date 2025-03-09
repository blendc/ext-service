import logging
from typing import Any, Dict, List, Optional, Type, Union, Callable

import marshmallow as ma
from marshmallow import Schema, fields, ValidationError

logger = logging.getLogger(__name__)

__all__ = (
    "BaseSchema",
    "serialize",
    "deserialize",
    "validate_schema",
)


class BaseSchema(Schema):

    class Meta:
        ordered = True
        strict = True
        unknown = ma.EXCLUDE
    
    @classmethod
    def serialize_many(cls, data: List[Any], **kwargs) -> List[Dict[str, Any]]:
        return cls(many=True, **kwargs).dump(data)
    
    @classmethod
    def serialize_one(cls, data: Any, **kwargs) -> Dict[str, Any]:
        return cls(**kwargs).dump(data)
    
    @classmethod
    def deserialize_many(cls, data: List[Dict[str, Any]], **kwargs) -> List[Any]:
        return cls(many=True, **kwargs).load(data)
    
    @classmethod
    def deserialize_one(cls, data: Dict[str, Any], **kwargs) -> Any:
        return cls(**kwargs).load(data)
    
    @classmethod
    def validate_many(cls, data: List[Dict[str, Any]], **kwargs) -> Dict[str, List[str]]:
        try:
            cls(many=True, **kwargs).validate(data)
            return {}
        except ValidationError as e:
            return e.messages
    
    @classmethod
    def validate_one(cls, data: Dict[str, Any], **kwargs) -> Dict[str, List[str]]:
        try:
            cls(**kwargs).validate(data)
            return {}
        except ValidationError as e:
            return e.messages


def serialize(
    data: Any,
    schema: Type[Schema],
    many: bool = False,
    **kwargs
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    if many:
        return schema(many=True, **kwargs).dump(data)
    return schema(**kwargs).dump(data)


def deserialize(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    schema: Type[Schema],
    many: bool = False,
    **kwargs
) -> Any:
    if many:
        return schema(many=True, **kwargs).load(data)
    return schema(**kwargs).load(data)


def validate_schema(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    schema: Type[Schema],
    many: bool = False,
    **kwargs
) -> Dict[str, List[str]]:
    try:
        if many:
            schema(many=True, **kwargs).validate(data)
        else:
            schema(**kwargs).validate(data)
        return {}
    except ValidationError as e:
        return e.messages


class TimestampField(fields.Field):

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        return int(value.timestamp())
    
    def _deserialize(self, value, attr, data, **kwargs):
        if value is None:
            return None
        from datetime import datetime
        return datetime.fromtimestamp(value)
