import json
import re

from .errors import ValidationError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
INTEGRATION_TYPES = ("webhook", "git", "ci", "calendar")


def require_fields(payload, fields):
    missing = [field for field in fields if payload.get(field) in (None, "")]
    if missing:
        raise ValidationError("Required fields are missing", {"fields": missing})


def normalize_email(email):
    value = str(email or "").strip().lower()
    if not EMAIL_RE.match(value):
        raise ValidationError("Email is invalid", {"email": email})
    return value


def validate_slug(slug, field="slug"):
    value = str(slug or "").strip().lower()
    if not SLUG_RE.match(value):
        raise ValidationError("Slug is invalid", {field: slug})
    return value


def validate_text(text, field, min_length=1, max_length=4000):
    value = str(text or "").strip()
    if len(value) < min_length or len(value) > max_length:
        raise ValidationError("Text length is invalid", {"field": field, "min": min_length, "max": max_length})
    return value


def validate_bool(value, field):
    if not isinstance(value, bool):
        raise ValidationError("Boolean value is invalid", {"field": field})
    return value


def validate_int(value, field, minimum=1):
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Integer value is invalid", {"field": field}) from exc
    if number < minimum:
        raise ValidationError("Integer value is too small", {"field": field, "minimum": minimum})
    return number


def validate_integration_type(value):
    if value not in INTEGRATION_TYPES:
        raise ValidationError("Integration type is invalid", {"type": value, "allowed": list(INTEGRATION_TYPES)})
    return value


def parse_config(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValidationError("Integration config must be valid JSON") from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValidationError("Integration config must be an object")
