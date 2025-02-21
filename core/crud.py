from core.http import *

def get_object_or_404(model_class, **kwargs):
    obj = model_class.get_or_none(**kwargs)
    if not obj:
        request_not_found(error="{} Not found".format(model_class.__name__))
    return obj

def get_object_or_400(model_class, **kwargs):
    obj = model_class.get_or_none(**kwargs)
    if not obj:
        request_bad(error="{} Not found".format(model_class.__name__))
    return obj

def get_object_or_422(model_class, **kwargs):
    obj = model_class.get_or_none(**kwargs)
    if not obj:
        request_unprocessable(error="{} Not found".format(model_class.__name__))
    return obj
