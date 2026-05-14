import base64
import hashlib
import hmac
import json
import os
import time

from .errors import AuthError, ValidationError


def _b64encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def hash_password(password, salt=None):
    if not isinstance(password, str) or len(password) < 8:
        raise ValidationError("Password must contain at least 8 characters")
    raw_salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), raw_salt, 120_000)
    return "pbkdf2_sha256${}${}".format(_b64encode(raw_salt), _b64encode(digest))


def verify_password(password, stored_hash):
    try:
        algorithm, salt_value, digest_value = stored_hash.split("$", 2)
    except ValueError as exc:
        raise AuthError("Stored password hash is invalid") from exc
    if algorithm != "pbkdf2_sha256":
        raise AuthError("Stored password hash uses unsupported algorithm")
    expected = hash_password(password, _b64decode(salt_value)).split("$", 2)[2]
    return hmac.compare_digest(expected, digest_value)


def issue_token(user, secret, ttl_seconds, now=None):
    issued_at = int(now if now is not None else time.time())
    payload = {
        "sub": user["id"],
        "email": user["email"],
        "role": user["role"],
        "iat": issued_at,
        "exp": issued_at + ttl_seconds,
    }
    data = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()
    return "{}.{}".format(_b64encode(data), _b64encode(signature))


def verify_token(token, secret, now=None):
    try:
        payload_part, signature_part = token.split(".", 1)
        data = _b64decode(payload_part)
        signature = _b64decode(signature_part)
    except Exception as exc:
        raise AuthError("Token is malformed") from exc
    expected = hmac.new(secret.encode("utf-8"), data, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, signature):
        raise AuthError("Token signature is invalid")
    payload = json.loads(data.decode("utf-8"))
    current_time = int(now if now is not None else time.time())
    if payload["exp"] < current_time:
        raise AuthError("Token has expired")
    return payload
