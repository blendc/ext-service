from webob import exc
import cerberus
from json.decoder import JSONDecodeError
import funcy as fn
from core.settings import FlexibleDict
from core.http import _raise_error, request_not_acceptable

__all__ = ("verify", )


@fn.decorator
def verify(
    call,
    validation_schema,
    source="json_body",
    error_class=exc.HTTPBadRequest,
    **kwargs):
    if source == "json_body":
        try:
            input_data = dict(call.req.json)
        except JSONDecodeError:
            request_not_acceptable(error="Invalid JSON Request")
    elif source == "params":
        input_data = dict(call.req.params)
    else:
        raise KeyError("Unknown data source")
    validator = cerberus.Validator(validation_schema, **kwargs)
    if not validator.validate(input_data):
        _raise_error(error_class, errors=validator.errors)
    call.req.data = FlexibleDict(validator.document)
    return call()
