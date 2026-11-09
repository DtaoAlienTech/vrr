from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
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

    # Admin login. Short access token, longer refresh token that is replaced on every use.
    access_token_minutes: int = Field(default=15, ge=1, le=120)
    refresh_token_days: int = Field(default=7, ge=1, le=90)
    # Cookies are "Secure" (https only) in production. Set COOKIE_SECURE=true/false to override.
    cookie_secure: bool | None = None
    cookie_domain: str | None = None
    # Name shown in the authenticator app next to the six-digit code.
    totp_issuer: str = "VRR Degree College"

    # Where uploaded photos and PDFs are stored. In Docker this is a shared volume that Caddy also
    # serves at /uploads. The website builds picture addresses from `uploads_url`.
    upload_dir: Path = ROOT / "uploads"
    uploads_url: str = "/uploads"
    # The photos exactly as they were uploaded (they may contain location data). Never served.
    originals_dir: Path = ROOT / "originals"
    max_upload_mb: int = Field(default=10, ge=1, le=50)

    # After a change in the admin, the backend tells the website which cached pages are out of date.
    revalidate_url: str = ""
    revalidate_secret: SecretStr | None = None

    # Enquiry form
    enquiry_to_email: str = ""
    enquiry_rate_limit_per_hour: int = Field(default=5, ge=1)
    turnstile_secret: SecretStr | None = None

    # Outgoing email. Optional: enquiries are always saved, even when email is not configured.
    smtp_host: str = ""
    smtp_port: int = 587
    # starttls = port 587 (most providers), ssl = port 465, none = only for a local test mailbox
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_user: str = ""
    smtp_password: SecretStr | None = None
    mail_from: str = ""

    @model_validator(mode="after")
    def _no_password_without_encryption(self) -> "Settings":
        if self.smtp_security == "none" and (self.smtp_user or self.smtp_password):
            raise ValueError(
                "SMTP_SECURITY=none never sends a password: use starttls or ssl with a login"
            )
        return self

    @model_validator(mode="after")
    def _strong_key_in_production(self) -> "Settings":
        if self.env == "prod" and len(self.secret_key) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return self

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cookies_secure(self) -> bool:
        return self.is_prod if self.cookie_secure is None else self.cookie_secure

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
