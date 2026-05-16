import json
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from .config import Settings
from .db import Database, row_to_dict
from .errors import AppError, AuthError, ConflictError, NotFoundError, ValidationError
from .rbac import is_staff, require_permission, require_user, validate_role
from .security import hash_password, issue_token, verify_password, verify_token
from .validators import (
    normalize_email,
    parse_config,
    require_fields,
    validate_bool,
    validate_int,
    validate_integration_type,
    validate_slug,
    validate_text,
)


@dataclass
class ApiResponse:
    status: int
    payload: dict
    headers: dict = field(default_factory=dict)

    def body(self):
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


class MessengerApp:
    def __init__(self, settings=None, database=None):
        self.settings = settings or Settings.from_env()
        self.db = database or Database(self.settings.database_url)
        self.db.migrate()

    def seed_demo(self):
        if self.db.one("SELECT id FROM users LIMIT 1"):
            return {"seeded": False}
        admin = self._create_user("admin@corp.test", "Admin", "AdminPass123", "admin")
        moderator = self._create_user("mod@corp.test", "Moderator", "ModeratorPass123", "moderator")
        alice = self._create_user("alice@corp.test", "Alice", "AlicePass123", "member")
        bot = self._create_user("deploy-bot@corp.test", "Deploy Bot", "DeployBot123", "bot")
        general = self._create_channel(admin, "general", "General", "Company-wide announcements", False)
        engineering = self._create_channel(moderator, "engineering", "Engineering", "Backend, frontend, and CI", False)
        security = self._create_channel(admin, "security", "Security", "Private incident coordination", True)
        for channel in (general, engineering, security):
            for user in (admin, moderator, alice, bot):
                self._add_member(channel["id"], user["id"], "member")
        self._create_message(admin, general["id"], "Welcome to the corporate messenger workspace.")
        self._create_message(alice, engineering["id"], "CI pipeline is green after the last migration.")
        self._create_integration(admin, general["id"], "Release webhook", "webhook", {"url": "https://example.test/hook"}, True)
        self._create_integration(moderator, engineering["id"], "Git mirror", "git", {"repo": "corp/messenger"}, True)
        self._audit(admin["id"], "seed", "workspace", None, {"users": 4, "channels": 3})
        return {"seeded": True}

    def handle(self, method, raw_path, headers=None, body=b""):
        headers = headers or {}
        try:
            parsed = urlparse(raw_path)
            path = parsed.path.rstrip("/") or "/"
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            payload = self._json_body(body)
            response = self._dispatch(method.upper(), path, query, headers, payload)
            response.headers.setdefault("Content-Type", "application/json; charset=utf-8")
            response.headers.setdefault("Access-Control-Allow-Origin", self.settings.cors_origin)
            return response
        except AppError as exc:
            return ApiResponse(exc.status, exc.to_payload(), {"Content-Type": "application/json; charset=utf-8"})
        except json.JSONDecodeError as exc:
            error = ValidationError("Request body must be valid JSON", {"reason": str(exc)})
            return ApiResponse(error.status, error.to_payload(), {"Content-Type": "application/json; charset=utf-8"})

    def _dispatch(self, method, path, query, headers, payload):
        if method == "OPTIONS":
            return ApiResponse(204, {}, {"Access-Control-Allow-Headers": "Authorization, Content-Type"})
        if method == "GET" and path == "/api/health":
            return ApiResponse(200, {"status": "ok", "factors": self.settings.factor_report()})
        if method == "POST" and path == "/api/seed":
            return ApiResponse(201, self.seed_demo())
        if method == "POST" and path == "/api/auth/login":
            return ApiResponse(200, self._login(payload))
        user = self._current_user(headers)
        if method == "GET" and path == "/api/auth/me":
            return ApiResponse(200, {"user": self._public_user(require_user(user))})
        parts = [part for part in path.split("/") if part]
        if parts[:1] == ["api"] and len(parts) >= 2:
            resource = parts[1]
            tail = parts[2:]
            if resource == "users":
                return self._users_route(method, tail, payload, user)
            if resource == "channels":
                return self._channels_route(method, tail, payload, user, query)
            if resource == "messages":
                return self._messages_route(method, tail, payload, user)
            if resource == "integrations":
                return self._integrations_route(method, tail, payload, user)
            if resource == "audit-events":
                return self._audit_route(method, tail, user)
        raise NotFoundError("Route not found")

    def _json_body(self, body):
        if body in (b"", "", None):
            return {}
        if isinstance(body, bytes):
            try:
                body = body.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValidationError("Request body must be UTF-8") from exc
        return json.loads(body)

    def _current_user(self, headers):
        authorization = headers.get("Authorization") or headers.get("authorization")
        if not authorization:
            return None
        if not authorization.startswith("Bearer "):
            raise AuthError("Authorization header must use Bearer token")
        token_payload = verify_token(authorization.replace("Bearer ", "", 1), self.settings.secret_key)
        row = self.db.require_one("SELECT * FROM users WHERE id = ?", (token_payload["sub"],), "user")
        return row_to_dict(row)

    def _login(self, payload):
        require_fields(payload, ("email", "password"))
        email = normalize_email(payload["email"])
        row = self.db.one("SELECT * FROM users WHERE email = ?", (email,))
        if row is None or not verify_password(payload["password"], row["password_hash"]):
            raise AuthError("Email or password is incorrect")
        user = row_to_dict(row)
        require_user(user)
        token = issue_token(user, self.settings.secret_key, self.settings.token_ttl_seconds)
        self._audit(user["id"], "login", "user", user["id"], {"email": email})
        return {"token": token, "user": self._public_user(user)}

    def _users_route(self, method, tail, payload, user):
        if method == "GET" and not tail:
            require_permission(user, "users:read")
            return ApiResponse(200, {"users": [self._public_user(row_to_dict(row)) for row in self.db.all("SELECT * FROM users ORDER BY id")]})
        if method == "POST" and not tail:
            actor = require_permission(user, "users:write")
            created = self._create_user(payload.get("email"), payload.get("name"), payload.get("password"), payload.get("role", "member"))
            self._audit(actor["id"], "create", "user", created["id"], {"email": created["email"], "role": created["role"]})
            return ApiResponse(201, {"user": self._public_user(created)})
        if len(tail) == 1 and tail[0].isdigit():
            user_id = int(tail[0])
            if method == "PATCH":
                actor = require_permission(user, "users:write")
                updated = self._update_user(user_id, payload)
                self._audit(actor["id"], "update", "user", user_id, {"fields": sorted(payload.keys())})
                return ApiResponse(200, {"user": self._public_user(updated)})
            if method == "DELETE":
                actor = require_permission(user, "users:write")
                self.db.execute("UPDATE users SET active = 0 WHERE id = ?", (user_id,))
                self._audit(actor["id"], "disable", "user", user_id, {})
                return ApiResponse(200, {"disabled": user_id})
        raise NotFoundError("User route not found")

    def _channels_route(self, method, tail, payload, user, query):
        current = require_user(user)
        if method == "GET" and not tail:
            rows = self.db.all("SELECT * FROM channels ORDER BY id")
            visible = [row_to_dict(row) for row in rows if self._can_read_channel(current, row["id"])]
            return ApiResponse(200, {"channels": visible, "filter": query.get("q", "")})
        if method == "POST" and not tail:
            actor = require_permission(current, "channels:write")
            created = self._create_channel(actor, payload.get("slug"), payload.get("name"), payload.get("description", ""), payload.get("is_private", False))
            self._add_member(created["id"], actor["id"], "owner")
            self._audit(actor["id"], "create", "channel", created["id"], {"slug": created["slug"]})
            return ApiResponse(201, {"channel": created})
        if len(tail) == 1 and tail[0].isdigit():
            channel_id = int(tail[0])
            if method == "GET":
                self._require_channel_read(current, channel_id)
                return ApiResponse(200, {"channel": self._get_channel(channel_id)})
            if method == "PATCH":
                actor = require_permission(current, "channels:write")
                updated = self._update_channel(channel_id, payload)
                self._audit(actor["id"], "update", "channel", channel_id, {"fields": sorted(payload.keys())})
                return ApiResponse(200, {"channel": updated})
            if method == "DELETE":
                actor = require_permission(current, "channels:write")
                self.db.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
                self._audit(actor["id"], "delete", "channel", channel_id, {})
                return ApiResponse(200, {"deleted": channel_id})
        if len(tail) == 2 and tail[0].isdigit() and tail[1] == "members" and method == "POST":
            actor = require_permission(current, "channels:write")
            require_fields(payload, ("user_id",))
            user_id = validate_int(payload["user_id"], "user_id")
            channel_id = int(tail[0])
            self._add_member(channel_id, user_id, payload.get("member_role", "member"))
            self._audit(actor["id"], "add_member", "channel", channel_id, {"user_id": user_id})
            return ApiResponse(201, {"added": user_id})
        if len(tail) == 2 and tail[0].isdigit() and tail[1] == "messages":
            channel_id = int(tail[0])
            if method == "GET":
                self._require_channel_read(current, channel_id)
                rows = self.db.all(
                    "SELECT messages.*, users.name AS author_name FROM messages JOIN users ON users.id = messages.author_id WHERE channel_id = ? ORDER BY messages.id",
                    (channel_id,),
                )
                return ApiResponse(200, {"messages": [row_to_dict(row) for row in rows]})
            if method == "POST":
                created = self._create_message(current, channel_id, payload.get("body"))
                self._audit(current["id"], "create", "message", created["id"], {"channel_id": channel_id})
                return ApiResponse(201, {"message": created})
        raise NotFoundError("Channel route not found")

    def _messages_route(self, method, tail, payload, user):
        current = require_user(user)
        if len(tail) == 1 and tail[0].isdigit():
            message_id = int(tail[0])
            message = self._get_message(message_id)
            if method == "PATCH":
                self._require_message_owner_or_staff(current, message)
                body = validate_text(payload.get("body"), "body", 1, 4000)
                self.db.execute("UPDATE messages SET body = ?, edited = 1 WHERE id = ?", (body, message_id))
                updated = self._get_message(message_id)
                self._audit(current["id"], "update", "message", message_id, {})
                return ApiResponse(200, {"message": updated})
            if method == "DELETE":
                self._require_message_owner_or_staff(current, message)
                self.db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
                self._audit(current["id"], "delete", "message", message_id, {})
                return ApiResponse(200, {"deleted": message_id})
        raise NotFoundError("Message route not found")

    def _integrations_route(self, method, tail, payload, user):
        current = require_permission(user, "integrations:write")
        if method == "GET" and not tail:
            rows = self.db.all("SELECT * FROM integrations ORDER BY id")
            return ApiResponse(200, {"integrations": [row_to_dict(row) for row in rows]})
        if method == "POST" and not tail:
            require_fields(payload, ("channel_id", "name", "type"))
            created = self._create_integration(
                current,
                validate_int(payload.get("channel_id"), "channel_id"),
                payload.get("name"),
                payload.get("type"),
                payload.get("config"),
                payload.get("enabled", True),
            )
            self._audit(current["id"], "create", "integration", created["id"], {"type": created["type"]})
            return ApiResponse(201, {"integration": created})
        if len(tail) == 1 and tail[0].isdigit():
            integration_id = int(tail[0])
            if method == "PATCH":
                updated = self._update_integration(integration_id, payload)
                self._audit(current["id"], "update", "integration", integration_id, {"fields": sorted(payload.keys())})
                return ApiResponse(200, {"integration": updated})
            if method == "DELETE":
                self.db.execute("DELETE FROM integrations WHERE id = ?", (integration_id,))
                self._audit(current["id"], "delete", "integration", integration_id, {})
                return ApiResponse(200, {"deleted": integration_id})
        raise NotFoundError("Integration route not found")

    def _audit_route(self, method, tail, user):
        require_permission(user, "audit:read")
        if method == "GET" and not tail:
            rows = self.db.all("SELECT * FROM audit_events ORDER BY id DESC")
            return ApiResponse(200, {"events": [row_to_dict(row) for row in rows]})
        raise NotFoundError("Audit route not found")

    def _create_user(self, email, name, password, role):
        normalized_email = normalize_email(email)
        clean_name = validate_text(name, "name", 2, 80)
        clean_role = validate_role(role)
        password_hash = hash_password(password)
        user_id = self.db.insert(
            "INSERT INTO users (email, name, password_hash, role, active) VALUES (?, ?, ?, ?, ?)",
            (normalized_email, clean_name, password_hash, clean_role, True),
        )
        return row_to_dict(self.db.require_one("SELECT * FROM users WHERE id = ?", (user_id,), "user"))

    def _update_user(self, user_id, payload):
        self.db.require_one("SELECT * FROM users WHERE id = ?", (user_id,), "user")
        updates = []
        parameters = []
        if "name" in payload:
            updates.append("name = ?")
            parameters.append(validate_text(payload["name"], "name", 2, 80))
        if "role" in payload:
            updates.append("role = ?")
            parameters.append(validate_role(payload["role"]))
        if "active" in payload:
            updates.append("active = ?")
            parameters.append(validate_bool(payload["active"], "active"))
        if not updates:
            raise ValidationError("No user fields to update")
        parameters.append(user_id)
        self.db.execute("UPDATE users SET {} WHERE id = ?".format(", ".join(updates)), tuple(parameters))
        return row_to_dict(self.db.require_one("SELECT * FROM users WHERE id = ?", (user_id,), "user"))

    def _create_channel(self, actor, slug, name, description, is_private):
        clean_slug = validate_slug(slug)
        clean_name = validate_text(name, "name", 2, 80)
        clean_description = validate_text(description or "No description", "description", 2, 240)
        private = validate_bool(is_private, "is_private")
        channel_id = self.db.insert(
            "INSERT INTO channels (slug, name, description, is_private, created_by) VALUES (?, ?, ?, ?, ?)",
            (clean_slug, clean_name, clean_description, private, actor["id"]),
        )
        return self._get_channel(channel_id)

    def _update_channel(self, channel_id, payload):
        self._get_channel(channel_id)
        updates = []
        parameters = []
        if "name" in payload:
            updates.append("name = ?")
            parameters.append(validate_text(payload["name"], "name", 2, 80))
        if "description" in payload:
            updates.append("description = ?")
            parameters.append(validate_text(payload["description"], "description", 2, 240))
        if "is_private" in payload:
            updates.append("is_private = ?")
            parameters.append(validate_bool(payload["is_private"], "is_private"))
        if not updates:
            raise ValidationError("No channel fields to update")
        parameters.append(channel_id)
        self.db.execute("UPDATE channels SET {} WHERE id = ?".format(", ".join(updates)), tuple(parameters))
        return self._get_channel(channel_id)

    def _get_channel(self, channel_id):
        return row_to_dict(self.db.require_one("SELECT * FROM channels WHERE id = ?", (channel_id,), "channel"))

    def _add_member(self, channel_id, user_id, member_role):
        self.db.require_one("SELECT id FROM channels WHERE id = ?", (channel_id,), "channel")
        self.db.require_one("SELECT id FROM users WHERE id = ?", (user_id,), "user")
        if member_role not in ("owner", "member"):
            raise ValidationError("Channel member role is invalid", {"member_role": member_role})
        self.db.execute(
            "INSERT OR IGNORE INTO channel_members (channel_id, user_id, member_role) VALUES (?, ?, ?)",
            (channel_id, user_id, member_role),
        )

    def _can_read_channel(self, user, channel_id):
        if is_staff(user):
            return True
        channel = self.db.require_one("SELECT is_private FROM channels WHERE id = ?", (channel_id,), "channel")
        if not channel["is_private"]:
            return True
        return self.db.one("SELECT 1 FROM channel_members WHERE channel_id = ? AND user_id = ?", (channel_id, user["id"])) is not None

    def _require_channel_read(self, user, channel_id):
        if not self._can_read_channel(user, channel_id):
            raise AuthError("Channel is private or unavailable")

    def _create_message(self, actor, channel_id, body):
        require_permission(actor, "messages:write")
        self._require_channel_read(actor, channel_id)
        clean_body = validate_text(body, "body", 1, 4000)
        message_id = self.db.insert(
            "INSERT INTO messages (channel_id, author_id, body) VALUES (?, ?, ?)",
            (channel_id, actor["id"], clean_body),
        )
        return self._get_message(message_id)

    def _get_message(self, message_id):
        row = self.db.require_one(
            "SELECT messages.*, users.name AS author_name FROM messages JOIN users ON users.id = messages.author_id WHERE messages.id = ?",
            (message_id,),
            "message",
        )
        return row_to_dict(row)

    def _require_message_owner_or_staff(self, user, message):
        if is_staff(user) or message["author_id"] == user["id"]:
            return
        require_permission(user, "messages:moderate")

    def _create_integration(self, actor, channel_id, name, integration_type, config, enabled):
        self._get_channel(channel_id)
        clean_name = validate_text(name, "name", 2, 80)
        clean_type = validate_integration_type(integration_type)
        clean_config = parse_config(config)
        clean_enabled = validate_bool(enabled, "enabled")
        integration_id = self.db.insert(
            "INSERT INTO integrations (channel_id, name, type, config_json, enabled, created_by) VALUES (?, ?, ?, ?, ?, ?)",
            (channel_id, clean_name, clean_type, json.dumps(clean_config, sort_keys=True), clean_enabled, actor["id"]),
        )
        return row_to_dict(self.db.require_one("SELECT * FROM integrations WHERE id = ?", (integration_id,), "integration"))

    def _update_integration(self, integration_id, payload):
        current = row_to_dict(self.db.require_one("SELECT * FROM integrations WHERE id = ?", (integration_id,), "integration"))
        updates = []
        parameters = []
        if "name" in payload:
            updates.append("name = ?")
            parameters.append(validate_text(payload["name"], "name", 2, 80))
        if "config" in payload:
            updates.append("config_json = ?")
            parameters.append(json.dumps(parse_config(payload["config"]), sort_keys=True))
        if "enabled" in payload:
            updates.append("enabled = ?")
            parameters.append(validate_bool(payload["enabled"], "enabled"))
        if not updates:
            return current
        parameters.append(integration_id)
        self.db.execute("UPDATE integrations SET {} WHERE id = ?".format(", ".join(updates)), tuple(parameters))
        return row_to_dict(self.db.require_one("SELECT * FROM integrations WHERE id = ?", (integration_id,), "integration"))

    def _audit(self, actor_id, action, entity, entity_id, metadata):
        self.db.insert(
            "INSERT INTO audit_events (actor_id, action, entity, entity_id, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (actor_id, action, entity, entity_id, json.dumps(metadata, sort_keys=True)),
        )

    def _public_user(self, user):
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "role": user["role"],
            "active": user["active"],
            "created_at": user["created_at"],
        }
