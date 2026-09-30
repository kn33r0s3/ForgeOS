import re
from typing import get_args, get_origin

from fastapi.routing import APIRoute
from pydantic import BaseModel

from app.api.public import router as public_router


_INTERNAL_FIELD = re.compile(
    r"(^|_)(score|confidence|quality|importance|reliability|risk|rank|ranking|probability|expected_value|owner_priority|unverified)(_|$)",
    re.IGNORECASE,
)


def _models_in(annotation):
    origin = get_origin(annotation)
    if origin is not None:
        for arg in get_args(annotation):
            yield from _models_in(arg)
        return
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation


def test_every_public_route_schema_excludes_internal_metrics():
    routes = [route for route in public_router.routes if isinstance(route, APIRoute)]
    assert routes, "public router has no typed routes to audit"
    missing_models = [route.path for route in routes if route.response_model is None]
    assert not missing_models, f"public routes need explicit response models: {missing_models}"

    pending_models = [
        model
        for route in routes
        for model in _models_in(route.response_model)
    ]
    checked_models = set()
    violations = []
    while pending_models:
        model = pending_models.pop()
        if model in checked_models:
            continue
        checked_models.add(model)
        for field_name, field in model.model_fields.items():
            if _INTERNAL_FIELD.search(field_name):
                violations.append(f"{model.__name__}.{field_name}")
            pending_models.extend(_models_in(field.annotation))

    assert not violations, "internal fields must stay out of public schemas: " + ", ".join(violations)
