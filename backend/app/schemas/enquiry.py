import re
import unicodedata
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

PHONE_PATTERN = re.compile(r"^[6-9][0-9]{9}$")  # Indian mobile numbers


def _has_control_chars(value: str, allowed: str = "") -> bool:
    return any(unicodedata.category(ch).startswith("C") and ch not in allowed for ch in value)


class EnquiryIn(BaseModel):
    """What the website form may send. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, StringConstraints(min_length=2, max_length=80)]
    phone: str
    course: Annotated[str, StringConstraints(max_length=120)] | None = None
    message: Annotated[str, StringConstraints(max_length=500)] | None = None
    source_page: Annotated[str, StringConstraints(max_length=200)] | None = None
    # Honeypot: real visitors never see this field, so it must stay empty.
    website: str = Field(default="", max_length=200)
    turnstile_token: str | None = Field(default=None, max_length=2048)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if _has_control_chars(value) or "<" in value or ">" in value:
            raise ValueError("Name contains characters that are not allowed")
        return value

    @field_validator("phone", mode="before")
    @classmethod
    def normalise_phone(cls, value: object) -> str:
        digits = re.sub(r"[\s\-()]", "", str(value))
        for prefix in ("+91", "0091", "91", "0"):
            if digits.startswith(prefix) and len(digits) - len(prefix) == 10:
                digits = digits[len(prefix) :]
                break
        if not PHONE_PATTERN.fullmatch(digits):
            raise ValueError("Enter a valid 10-digit mobile number")
        return digits

    @field_validator("message", "course", "source_page")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        if _has_control_chars(value, allowed="\n\t"):
            raise ValueError("Text contains characters that are not allowed")
        return value
