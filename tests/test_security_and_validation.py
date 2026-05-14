import json
import tempfile
import unittest

from server.config import Settings
from server.db import Database, row_to_dict
from server.errors import AuthError, ValidationError
from server.rbac import can, require_permission, require_user, validate_role
from server.security import hash_password, issue_token, verify_password, verify_token
from server.validators import (
    normalize_email,
    parse_config,
    require_fields,
    validate_bool,
    validate_int,
    validate_integration_type,
    validate_slug,
    validate_text,
)


class SecurityAndValidationTest(unittest.TestCase):
    def test_settings_from_env_and_factor_report(self):
        settings = Settings.from_env(
            {
                "APP_ENV": "production",
                "DATABASE_URL": "sqlite:///data/app.db",
                "SECRET_KEY": "secret",
                "PORT": "9090",
                "TOKEN_TTL_SECONDS": "12",
                "CORS_ORIGIN": "https://example.test",
            }
        )
        self.assertEqual(settings.port, 9090)
        self.assertEqual(settings.token_ttl_seconds, 12)
        self.assertEqual(settings.factor_report()["backing_services"], "database_url")

    def test_database_rejects_unsupported_url(self):
        with self.assertRaises(ValueError):
            Database("postgres://example")

    def test_database_accepts_file_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db = Database(f"sqlite:///{tmpdir}/data/app.db")
            self.assertTrue(db._sqlite_path(f"sqlite:///{tmpdir}/data/app.db").endswith("data/app.db"))
            db.close()

    def test_row_to_dict_decodes_json_and_booleans(self):
        db = Database("sqlite:///:memory:")
        db.execute("CREATE TABLE sample (id INTEGER, active INTEGER, metadata_json TEXT)")
        db.execute("INSERT INTO sample VALUES (1, 1, ?)", (json.dumps({"a": 1}),))
        self.assertEqual(row_to_dict(db.one("SELECT * FROM sample")), {"id": 1, "active": True, "metadata": {"a": 1}})

    def test_password_hash_and_verify(self):
        stored = hash_password("StrongPass123", b"1234567890abcdef")
        self.assertTrue(verify_password("StrongPass123", stored))
        self.assertFalse(verify_password("WrongPass123", stored))

    def test_password_validation_and_bad_stored_hashes(self):
        with self.assertRaises(ValidationError):
            hash_password("short")
        with self.assertRaises(AuthError):
            verify_password("StrongPass123", "broken")
        with self.assertRaises(AuthError):
            verify_password("StrongPass123", "plain$abc$def")

    def test_token_lifecycle_and_failures(self):
        user = {"id": 7, "email": "a@b.test", "role": "admin"}
        token = issue_token(user, "secret", 10, now=100)
        self.assertEqual(verify_token(token, "secret", now=101)["sub"], 7)
        with self.assertRaises(AuthError):
            verify_token("not-a-token", "secret", now=101)
        with self.assertRaises(AuthError):
            verify_token(token + "x", "secret", now=101)
        with self.assertRaises(AuthError):
            verify_token(token, "secret", now=111)

    def test_rbac_helpers(self):
        admin = {"role": "admin", "active": True}
        disabled = {"role": "member", "active": False}
        self.assertEqual(validate_role("bot"), "bot")
        self.assertTrue(can("admin", "audit:read"))
        self.assertFalse(can("member", "audit:read"))
        self.assertIs(require_user(admin), admin)
        self.assertIs(require_permission(admin, "audit:read"), admin)
        with self.assertRaises(ValidationError):
            validate_role("owner")
        with self.assertRaises(AuthError):
            require_user(None)
        with self.assertRaises(AuthError):
            require_user(disabled)
        with self.assertRaises(Exception):
            require_permission({"role": "member", "active": True}, "audit:read")

    def test_validators_accept_and_reject_payloads(self):
        payload = {"email": "Admin@Corp.Test", "enabled": True}
        require_fields(payload, ("email", "enabled"))
        self.assertEqual(normalize_email(payload["email"]), "admin@corp.test")
        self.assertEqual(validate_slug("release-room"), "release-room")
        self.assertEqual(validate_text(" hello ", "body"), "hello")
        self.assertTrue(validate_bool(True, "enabled"))
        self.assertEqual(validate_int("7", "id"), 7)
        self.assertEqual(validate_integration_type("ci"), "ci")
        self.assertEqual(parse_config('{"x": 1}'), {"x": 1})
        self.assertEqual(parse_config({"x": 1}), {"x": 1})
        self.assertEqual(parse_config(None), {})
        invalid_calls = [
            lambda: require_fields({}, ("missing",)),
            lambda: normalize_email("not-email"),
            lambda: validate_slug("-bad"),
            lambda: validate_text("", "body"),
            lambda: validate_bool("true", "enabled"),
            lambda: validate_int("bad", "id"),
            lambda: validate_int(0, "id"),
            lambda: validate_integration_type("sms"),
            lambda: parse_config("[1, 2]"),
            lambda: parse_config("{bad"),
            lambda: parse_config(3),
        ]
        for call in invalid_calls:
            with self.subTest(call=call):
                with self.assertRaises(ValidationError):
                    call()
