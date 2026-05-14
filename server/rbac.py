from .errors import AuthError, ForbiddenError, ValidationError

ROLES = ("admin", "moderator", "member", "bot")

PERMISSIONS = {
    "admin": {
        "users:read",
        "users:write",
        "channels:write",
        "messages:write",
        "messages:moderate",
        "integrations:write",
        "audit:read",
    },
    "moderator": {
        "channels:write",
        "messages:write",
        "messages:moderate",
        "integrations:write",
    },
    "member": {
        "messages:write",
    },
    "bot": {
        "messages:write",
    },
}


def validate_role(role):
    if role not in ROLES:
        raise ValidationError("Unknown role", {"role": role, "allowed": list(ROLES)})
    return role


def can(role, permission):
    return permission in PERMISSIONS.get(role, set())


def require_user(user):
    if user is None:
        raise AuthError("Authentication required")
    if not user["active"]:
        raise AuthError("User is disabled")
    return user


def require_permission(user, permission):
    current = require_user(user)
    if not can(current["role"], permission):
        raise ForbiddenError("Permission denied", {"permission": permission, "role": current["role"]})
    return current


def is_staff(user):
    return user is not None and user["role"] in ("admin", "moderator")
