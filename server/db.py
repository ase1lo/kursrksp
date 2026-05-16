import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

from .errors import ConflictError, NotFoundError


SCHEMA_SQLITE = """
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

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channels (
    id SERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    is_private BOOLEAN NOT NULL DEFAULT FALSE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS channel_members (
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    member_role TEXT NOT NULL DEFAULT 'member',
    PRIMARY KEY (channel_id, user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES users(id),
    body TEXT NOT NULL,
    edited BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS integrations (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    config_json TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    actor_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    metadata_json TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    def __init__(self, database_url):
        self.database_url = database_url
        self.driver = None
        self.integrity_error = sqlite3.IntegrityError
        self.connection = self._connect(database_url)

    def _connect(self, database_url):
        if database_url.startswith(("postgresql://", "postgres://")):
            return self._connect_postgres(database_url)
        path = self._sqlite_path(database_url)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        self.driver = "sqlite"
        self.integrity_error = sqlite3.IntegrityError
        return connection

    def _connect_postgres(self, database_url):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:
            raise RuntimeError("PostgreSQL support requires installing psycopg[binary]") from exc
        self.driver = "postgresql"
        self.integrity_error = psycopg.IntegrityError
        return psycopg.connect(database_url, row_factory=dict_row)

    def _sqlite_path(self, database_url):
        if database_url == "sqlite:///:memory:":
            return ":memory:"
        if database_url.startswith("sqlite:///"):
            return database_url.replace("sqlite:///", "", 1)
        raise ValueError("DATABASE_URL must start with postgresql://, postgres://, or sqlite:/// for tests")

    def migrate(self):
        if self.driver == "postgresql":
            for statement in self._postgres_schema_statements():
                self.connection.execute(statement)
            self.connection.commit()
        else:
            self.connection.executescript(SCHEMA_SQLITE)
            self.connection.commit()

    def execute(self, sql, parameters=()):
        try:
            cursor = self.connection.execute(self._sql(sql), parameters)
            self.connection.commit()
            return cursor
        except self.integrity_error as exc:
            self.connection.rollback()
            raise ConflictError("Database constraint failed", {"reason": str(exc)}) from exc

    def one(self, sql, parameters=()):
        return self.connection.execute(self._sql(sql), parameters).fetchone()

    def all(self, sql, parameters=()):
        return self.connection.execute(self._sql(sql), parameters).fetchall()

    def insert(self, sql, parameters=()):
        if self.driver == "postgresql":
            insert_sql = self._sql(sql)
            if " RETURNING " not in insert_sql.upper():
                insert_sql = "{} RETURNING id".format(insert_sql)
            try:
                cursor = self.connection.execute(insert_sql, parameters)
                row = cursor.fetchone()
                self.connection.commit()
                return row["id"]
            except self.integrity_error as exc:
                self.connection.rollback()
                raise ConflictError("Database constraint failed", {"reason": str(exc)}) from exc
        return self.execute(sql, parameters).lastrowid

    def require_one(self, sql, parameters=(), label="record"):
        row = self.one(sql, parameters)
        if row is None:
            raise NotFoundError("{} not found".format(label))
        return row

    def close(self):
        self.connection.close()

    def _sql(self, sql):
        if self.driver != "postgresql":
            return sql
        converted = sql.replace("?", "%s")
        if converted.startswith("INSERT OR IGNORE INTO"):
            converted = converted.replace("INSERT OR IGNORE INTO", "INSERT INTO", 1)
            converted = "{} ON CONFLICT DO NOTHING".format(converted)
        return converted

    def _postgres_schema_statements(self):
        return [statement.strip() for statement in SCHEMA_POSTGRES.split(";") if statement.strip()]


def row_to_dict(row):
    result = dict(row)
    for key, value in list(result.items()):
        if key.endswith("_json") and isinstance(value, str):
            result[key[:-5]] = json.loads(value)
            del result[key]
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        if key in ("active", "is_private", "enabled", "edited"):
            result[key] = bool(value)
    return result
