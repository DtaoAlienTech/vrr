from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> repo root is three levels above this folder
ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """All configuration comes from environment variables (or the root .env in development)."""

    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    env: Literal["dev", "prod"] = "dev"
    database_url: str
    secret_key: str = Field(min_length=16)
    allowed_hosts: str = "localhost,127.0.0.1"
    api_prefix: str = "/api/v1"
    # How many of our own reverse proxies (Next.js proxy, Caddy) sit in front of the API. Each one
    # appends the address it saw to X-Forwarded-For. 0 = ignore that header. Never set this higher
    # than the real number of proxies, or visitors could fake their address.
    trusted_proxy_hops: int = Field(default=0, ge=0, le=5)

    # Enquiry form
    enquiry_to_email: str = ""
    enquiry_rate_limit_per_hour: int = Field(default=5, ge=1)
    turnstile_secret: SecretStr | None = None

    # Outgoing email. Optional: enquiries are always saved, even when email is not configured.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr | None = None
    mail_from: str = ""

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def turnstile_enabled(self) -> bool:
        return bool(self.turnstile_secret and self.turnstile_secret.get_secret_value())

    @property
    def email_enabled(self) -> bool:
        return bool(self.smtp_host and self.enquiry_to_email and self.mail_from)


@lru_cache
def get_settings() -> Settings:
    return Settings()
