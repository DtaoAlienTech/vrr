from datetime import datetime
from typing import Any

from pydantic import model_validator

from app.schemas.common import AltText, CamelModel
from app.schemas.public import MediaVariantOut, Out


class MediaUpdateIn(CamelModel):
    alt_text: AltText | None = None
    crop_bottom: bool | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> "MediaUpdateIn":
        if self.alt_text is None and self.crop_bottom is None:
            raise ValueError("send altText and/or cropBottom")
        return self


class MediaAdminOut(Out):
    id: int
    kind: str
    original_filename: str
    alt_text: str
    mime: str
    size_bytes: int
    width: int | None = None
    height: int | None = None
    url: str
    thumb_url: str
    variants: list[MediaVariantOut]
    crop_bottom: bool
    created_at: datetime


class MediaUsageOut(Out):
    entity: str
    id: int
    label: str


class MediaUsageListOut(Out):
    usages: list[MediaUsageOut]


def media_admin_dict(row: Any, uploads_url: str) -> dict[str, Any]:
    prefix = uploads_url.rstrip("/")
    variants = [{"url": f"{prefix}/{v['name']}", "width": v["width"]} for v in row.variants]
    url = f"{prefix}/{row.stored_name}"
    return {
        "id": row.id,
        "kind": row.kind,
        "original_filename": row.original_filename,
        "alt_text": row.alt_text,
        "mime": row.mime,
        "size_bytes": row.size_bytes,
        "width": row.width,
        "height": row.height,
        "url": url,
        "thumb_url": variants[0]["url"] if variants else url,
        "variants": variants,
        "crop_bottom": row.crop_bottom,
        "created_at": row.created_at,
    }
