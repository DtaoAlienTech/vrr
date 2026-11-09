"""Loads the starter content into an empty database: college details, menu, courses, photos,
activities and the pages built from the approved design. Everything passes through the same
validation as the admin panel will use, so the starter content cannot break the rules."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    ActivityPhoto,
    Course,
    Department,
    Faculty,
    GalleryItem,
    Media,
    News,
    Page,
    PageSection,
    SiteSetting,
)
from app.schemas.blocks import validate_section
from app.schemas.common import check_rich_doc
from app.schemas.settings import validate_settings
from app.services.media import Storage, reprocess_media

SEED_DIR = Path(__file__).parent
_PUBLISHED = "published"


def is_empty(db: Session) -> bool:
    return db.scalar(select(func.count()).select_from(Page)) == 0


def _with_media_ids(data: Any, ids: dict[str, int]) -> Any:
    """Replaces {"mediaKey": "campus-1"} by {"mediaId": 12} once the photo has a database id."""
    if isinstance(data, dict):
        if set(data) == {"mediaKey"}:
            return {"mediaId": ids[data["mediaKey"]]}
        return {key: _with_media_ids(value, ids) for key, value in data.items()}
    if isinstance(data, list):
        return [_with_media_ids(value, ids) for value in data]
    return data


def _published_at(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T09:00:00+05:30")  # 9 am India time


def load_seed(db: Session, upload_dir: Path, *, make_copies: bool = True) -> dict[str, int]:
    """Adds the starter content (no commit). Raises if content already exists.
    `make_copies` also creates the resized WebP copies of the photos (tests skip it for speed)."""
    if not is_empty(db):
        raise RuntimeError(
            "The database already has pages; the starter content is not added again."
        )
    content = json.loads((SEED_DIR / "content.json").read_text(encoding="utf-8"))
    upload_dir.mkdir(parents=True, exist_ok=True)

    # ---- photos: copy the files, one library entry each ----
    ids: dict[str, int] = {}
    for item in content["media"]:
        stored_name = f"seed-{item['file']}"
        source = SEED_DIR / "photos" / item["file"]
        shutil.copyfile(source, upload_dir / stored_name)
        row = Media(
            kind="image",
            original_filename=item["file"],
            stored_name=stored_name,
            mime=item["mime"],
            size_bytes=source.stat().st_size,
            width=item["width"],
            height=item["height"],
            alt_text=item["alt"],
            crop_bottom=item["cropBottom"],
        )
        db.add(row)
        db.flush()
        if make_copies:
            reprocess_media(row, Storage(upload_dir, None))
        ids[item["key"]] = row.id

    # ---- site settings ----
    for group, data in content["settings"].items():
        db.add(SiteSetting(key=group, value=validate_settings(group, _with_media_ids(data, ids))))

    # ---- departments, courses, faculty ----
    departments: dict[str, Department] = {}
    for order, item in enumerate(content["departments"]):
        departments[item["slug"]] = Department(
            name=item["name"], slug=item["slug"], sort_order=order
        )
    db.add_all(departments.values())
    db.flush()
    for order, item in enumerate(content["courses"]):
        description = item.get("description")
        if description:
            check_rich_doc(description)
        db.add(
            Course(
                department_id=departments[item["department"]].id,
                name=item["name"],
                tab=item["tab"],
                slug=item["slug"],
                duration_years=item["durationYears"],
                affiliation=item.get("affiliation"),
                summary=item["summary"],
                description=description,
                subjects=item.get("subjects", []),
                eligibility=item.get("eligibility"),
                seats=item.get("seats"),
                fees=item.get("fees"),
                sort_order=order,
            )
        )
    for order, item in enumerate(content["faculty"]):
        db.add(
            Faculty(
                department_id=departments[item["department"]].id,
                name=item["name"],
                designation=item["designation"],
                qualification=item["qualification"],
                sort_order=order,
            )
        )

    # ---- activities, news, gallery ----
    for order, item in enumerate(content["activities"]):
        activity = Activity(
            title=item["title"],
            slug=item["slug"],
            group=item["group"],
            year=item.get("year"),
            summary=item["summary"],
            cover_media_id=ids[item["cover"]],
            show_on_home=item["showOnHome"],
            status=_PUBLISHED,
            sort_order=order,
        )
        for position, photo in enumerate(item["photos"]):
            activity.photos.append(
                ActivityPhoto(
                    media_id=ids[photo["media"]], caption=photo.get("caption"), sort_order=position
                )
            )
        db.add(activity)
    for item in content["news"]:
        check_rich_doc(item["body"])
        db.add(
            News(
                title=item["title"],
                slug=item["slug"],
                category=item["category"],
                summary=item["summary"],
                body=item["body"],
                published_at=_published_at(item["publishedAt"]),
                is_pinned=item["pinned"],
                status=_PUBLISHED,
            )
        )
    for order, item in enumerate(content["gallery"]):
        db.add(
            GalleryItem(
                kind="photo",
                media_id=ids[item["media"]],
                category=item["category"],
                caption=item["caption"],
                sort_order=order,
            )
        )

    # ---- pages and their sections ----
    now = datetime.now(UTC)
    for item in content["pages"]:
        page = Page(
            key=item["key"],
            title=item["title"],
            slug=item["slug"],
            seo_title=item.get("seoTitle"),
            seo_description=item.get("seoDescription"),
            og_media_id=ids[item["ogMedia"]] if item.get("ogMedia") else None,
            robots_noindex=item["noindex"],
            status=_PUBLISHED,
            published_at=now,
        )
        for position, section in enumerate(item["sections"]):
            data = validate_section(section["type"], _with_media_ids(section["data"], ids))
            page.sections.append(PageSection(type=section["type"], position=position, data=data))
        db.add(page)

    db.flush()
    return {
        "photos": len(content["media"]),
        "pages": len(content["pages"]),
        "courses": len(content["courses"]),
        "faculty": len(content["faculty"]),
        "activities": len(content["activities"]),
        "news": len(content["news"]),
        "gallery": len(content["gallery"]),
    }
