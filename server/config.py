import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_env: str
    database_url: str
    secret_key: str
    port: int
    token_ttl_seconds: int
    cors_origin: str

    @classmethod
    def from_env(cls, env=None):
        source = env or os.environ
        return cls(
            app_env=source.get("APP_ENV", "development"),
            database_url=source.get("DATABASE_URL", "sqlite:///messenger.db"),
            secret_key=source.get("SECRET_KEY", "dev-secret-change-me"),
            port=int(source.get("PORT", "8080")),
            token_ttl_seconds=int(source.get("TOKEN_TTL_SECONDS", "86400")),
            cors_origin=source.get("CORS_ORIGIN", "*"),
        )

    def factor_report(self):
        return {
            "config": "environment",
            "backing_services": "database_url",
            "port_binding": self.port,
            "env": self.app_env,
            "logs": "stdout",
        }
