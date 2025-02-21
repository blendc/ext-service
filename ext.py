import re
from webob import Response, exc
from webob.dec import wsgify

__all__ = ("AdvancedRouter",)


regex = {
    "shortuuid": r"[2-9A-HJ-NP-Za-km-z]{22}",
}


class FlexibleDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


split_arguments = lambda args: map(lambda x: x.strip(), args.split(","))
split_key_value_arguments = lambda args, **defaults: dict(
    defaults,
    **dict(map(lambda x: x.split("="), map(lambda x: x.strip(), args.split(","))))
)


class AdvancedRouter(list):
    def __init__(self):
        self.route_dict = dict()
        self.before_callbacks = CallbackRegistry()
        self.after_callbacks = CallbackRegistry()
        super().__init__()

    def find_route(self, req):
        matched = False
        for (pattern, handler, allowed_methods, uri_template, options) in self:
            match = pattern.match(req.path_info)
            if match:
                matched = True
                if req.method in allowed_methods:
                    return (handler, match.groupdict(), options)

        if matched:
            raise exc.HTTPMethodNotAllowed
        raise exc.HTTPNotFound

    def modify_response(self, response, **options):
        return response

    @wsgify
    def app(self, req):
        (handler, params, options) = self.find_route(req)
        req.options = FlexibleDict(options)
        for callback in self.before_callbacks:
            callback(req)
        response = handler(req, **params)
        for callback in self.after_callbacks:
            callback(req)
        return self.modify_response(response, **options)

    def add(self, uri_template, methods=["HEAD", "GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], route_name=None,
            **options):
        if route_name:
            self.route_dict[route_name] = convert_template_to_string(uri_template)

        def route_decorator(handler):
            self.append((re.compile(convert_template_to_regex(uri_template)), handler, methods, uri_template, options))
            return handler

        return route_decorator

    def head(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["HEAD"], route_name=route_name, **options)

    def get(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["GET"], route_name=route_name, **options)

    def post(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["POST"], route_name=route_name, **options)

    def put(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["PUT"], route_name=route_name, **options)

    def patch(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["PATCH"], route_name=route_name, **options)

    def delete(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["DELETE"], route_name=route_name, **options)

    def options(self, uri_template, route_name=None, **options):
        return self.add(uri_template, methods=["OPTIONS"], route_name=route_name, **options)


class JSONResponseRouter(AdvancedRouter):
    def modify_response(self, response, **options):
        if type(response) == Response:
            return response
        return Response(json_body=response,
                        content_type="application/json",
                        status=options.get("status", 200))


class CallbackRegistry(list):
    def __call__(self):
        def callback_decorator(callback):
            self.append(callback)
            return callback
        return callback_decorator


def convert_template_to_regex(template):
    regex = ""
    last_pos = 0
    var_pattern = re.compile(
        r"""
        \<          # The exact character "<"
        (\w+)       # The variable name (restricted to a-z, 0-9, _)
        (?::(\w+)(\((.*)\))?)? # The optional part
        \>          # The exact character ">"
        """,
        re.VERBOSE,
    )
    for match in var_pattern.finditer(template):
        regex += re.escape(template[last_pos: match.start()])
        var_name = match.group(1)
        type_of_var = match.group(2) or "basic"
        extra_args = match.group(4)
        args = [x.strip() for x in extra_args.split(",") if len(x.split("=")) == 1] if extra_args else ()
        kwargs = dict([[x.strip() for x in x.split("=")] for x in extra_args.split(",") if
                       len(x.split("=")) == 2]) if extra_args else {}
        pattern_func = globals().get(f"{type_of_var}_only")
        if not pattern_func:
            raise KeyError(f"Unknown pattern type {type_of_var}")
        expr = f"(?P<{var_name}>{pattern_func(*args, **kwargs)})"
        regex += expr
        last_pos = match.end()
    regex += re.escape(template[last_pos:])
    regex = "^%s$" % regex
    return regex


def convert_template_to_string(template):
    result_string = ""
    last_pos = 0
    var_pattern = re.compile(
        r"""
        \<          # The exact character "<"
        (\w+)       # The variable name (restricted to a-z, 0-9, _)
        (?::(\w+)(\((.*)\))?)? # The optional part
        \>          # The exact character ">"
        """,
        re.VERBOSE,
    )
    for match in var_pattern.finditer(template):
        result_string += template[last_pos: match.start()]
        var_name = match.group(1)
        result_string += "{{{}}}".format(var_name)
        last_pos = match.end()
    result_string += template[last_pos:]
    return result_string
