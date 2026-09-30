"""Single authoritative resolver and JSON Schema validator for substrate types."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError
from sqlalchemy.orm import Session

from app import models


class SubstrateError(ValueError):
    """A substrate record violates its registry or validation contract."""


def resolve_type(
    db: Session,
    category: str,
    type_name: str,
    *,
    require_active: bool = True,
) -> models.TypeRegistry:
    """Resolve exactly one registered type and optionally require it active."""
    name = (type_name or "").strip().lower()
    row = db.query(models.TypeRegistry).filter_by(category=category, type_name=name).one_or_none()
    if row is None:
        raise SubstrateError(f"unknown {category} {name!r} in type_registry")
    if require_active and row.status != "active":
        raise SubstrateError(f"{category} {name!r} is {row.status}, not active in type_registry")
    return row


def validate_schema(schema: Any) -> None:
    """Fail closed unless ``schema`` is a well-formed Draft 2020-12 schema."""
    try:
        Draft202012Validator.check_schema(schema)
    except (SchemaError, TypeError, ValueError) as exc:
        message = getattr(exc, "message", str(exc))
        raise SubstrateError(f"malformed JSON Schema: {message}") from exc


def validate_attributes(
    db: Session,
    category: str,
    type_name: str,
    attributes: Mapping[str, Any],
) -> models.TypeRegistry:
    """Resolve an active type and validate its JSON attributes before persistence."""
    if not isinstance(attributes, Mapping):
        raise SubstrateError("attributes must be a JSON object")
    row = resolve_type(db, category, type_name)
    try:
        schema = json.loads(row.schema_json)
    except (json.JSONDecodeError, TypeError) as exc:
        raise SubstrateError(f"malformed JSON Schema for {category} {type_name!r}") from exc
    validate_schema(schema)
    try:
        errors = sorted(
            Draft202012Validator(schema).iter_errors(dict(attributes)),
            key=lambda error: (list(error.absolute_path), error.message),
        )
    except (SchemaError, TypeError, ValueError) as exc:
        raise SubstrateError(f"malformed JSON Schema for {category} {type_name!r}: {exc}") from exc
    if errors:
        error = errors[0]
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        raise SubstrateError(f"invalid {category} {type_name!r} attributes at {path}: {error.message}")
    return row
