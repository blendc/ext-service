import logging
import funcy as fu
from ext import JSONResponseRouter
from webob import Response, exc
import ext
import builtins

logger = logging.getLogger(__name__)

__all__ = (
    "web_router",
    "request_bad",
    "request_unauthorized",
    "request_forbidden",
    "request_not_found",
    "request_not_acceptable",
    "request_unprocessable",
    "request_expectation_failed",
    "request_bad_gateway",
    "verify_json",
    "response_no_content",
    "response_created",
)

web_router = JSONResponseRouter()
ext.regex()["shortuuid"] = r"[2-9A-HJ-NP-Za-km-z]{22}"


def _raise_error(
    error_class,
    _default_msg="Generic Error",
    error_details=None,
    custom_error=None,
):
    raise error_class(
        json={"errors": error_details or {"__all__": [custom_error or _default_msg]}},
        content_type="application/json",
    )


def request_bad(**kwargs):
    _raise_error(exc.HTTPBadRequest, _default_msg="Bad Request", **kwargs)


def request_unauthorized(**kwargs):
    _raise_error(exc.HTTPUnauthorized, _default_msg="Unauthorized", **kwargs)


def request_forbidden(**kwargs):
    _raise_error(exc.HTTPForbidden, _default_msg="Forbidden", **kwargs)


def request_not_found(**kwargs):
    _raise_error(exc.HTTPNotFound, _default_msg="Not Found", **kwargs)


def request_not_acceptable(**kwargs):
    _raise_error(exc.HTTPNotAcceptable, _default_msg="Not Acceptable", **kwargs)


def request_unprocessable(**kwargs):
    _raise_error(
        exc.HTTPUnprocessableEntity, _default_msg="Unprocessable Entity", **kwargs
    )


def request_expectation_failed(**kwargs):
    _raise_error(exc.HTTPExpectationFailed, _default_msg="Expectation Failed", **kwargs)


def request_bad_gateway(**kwargs):
    _raise_error(exc.HTTPBadGateway, _default_msg="Bad Gateway", **kwargs)


@fu.decorator
def verify_json(call):
    try:
        call.req.json
    except:
        request_not_acceptable(custom_error="Invalid JSON request")
    return call()


@fu.decorator
def response_no_content(call):
    call()
    return Response(status=204)


@fu.decorator
def response_created(call):
    call()
    return Response(status=201)
