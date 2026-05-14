import json
import sqlite3
from pathlib import Path

from .errors import ConflictError, NotFoundError


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    is_private INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_members (
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    member_role TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (channel_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    edited INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS integrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, database_url):
        self.database_url = database_url
        self.connection = self._connect(database_url)

    def _connect(self, database_url):
        path = self._sqlite_path(database_url)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _sqlite_path(self, database_url):
        if database_url == "sqlite:///:memory:":
            return ":memory:"
        if database_url.startswith("sqlite:///"):
            return database_url.replace("sqlite:///", "", 1)
        raise ValueError("Only sqlite:/// URLs are supported by this educational build")

    def migrate(self):
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def execute(self, sql, parameters=()):
        try:
            cursor = self.connection.execute(sql, parameters)
            self.connection.commit()
            return cursor
        except sqlite3.IntegrityError as exc:
            raise ConflictError("Database constraint failed", {"reason": str(exc)}) from exc

    def one(self, sql, parameters=()):
        return self.connection.execute(sql, parameters).fetchone()

    def all(self, sql, parameters=()):
        return self.connection.execute(sql, parameters).fetchall()

    def insert(self, sql, parameters=()):
        return self.execute(sql, parameters).lastrowid

    def require_one(self, sql, parameters=(), label="record"):
        row = self.one(sql, parameters)
        if row is None:
            raise NotFoundError("{} not found".format(label))
        return row

    def close(self):
        self.connection.close()


def row_to_dict(row):
    result = dict(row)
    for key, value in list(result.items()):
        if key.endswith("_json") and isinstance(value, str):
            result[key[:-5]] = json.loads(value)
            del result[key]
        if key in ("active", "is_private", "enabled", "edited"):
            result[key] = bool(value)
    return result
