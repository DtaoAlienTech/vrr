"""The media library API: uploading, listing, editing alt text and deleting (only when unused)."""

import io
import os
import stat
import time
from dataclasses import dataclass
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.config import get_settings
from app.models import (
    Activity,
    ActivityPhoto,
    AuditLog,
    Course,
    Department,
    Faculty,
    GalleryItem,
    Media,
    News,
    NewsAttachment,
    Page,
    PageSection,
    SiteSetting,
)
from app.services import media as media_service
from app.services import revalidate
from tests.helpers import changes, signed_in

URL = "/api/v1/admin/media"
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"
TOKEN_FILE = r"^[0-9a-f]{24}-\d+\.webp$"


@dataclass
class Dirs:
    uploads: Path
    originals: Path

    def served(self) -> list[str]:
        return sorted(p.name for p in self.uploads.iterdir()) if self.uploads.exists() else []

    def private(self) -> list[str]:
        return sorted(p.name for p in self.originals.iterdir()) if self.originals.exists() else []


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch, empty_content) -> Dirs:
    """Uploads go to a temporary folder, the limit is 1 MB, and the library starts empty."""
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("ORIGINALS_DIR", str(tmp_path / "originals"))
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    get_settings.cache_clear()
    yield Dirs(tmp_path / "uploads", tmp_path / "originals")
    get_settings.cache_clear()


@pytest.fixture
def refreshes(monkeypatch) -> list[list[str]]:
    """Records the 'refresh these pages' messages instead of sending them."""
    sent: list[list[str]] = []
    monkeypatch.setattr(revalidate, "notify", lambda settings, tags, **_: sent.append(tags) or True)
    return sent


@pytest.fixture
def staff(api, make_user) -> str:
    make_user()
    return signed_in(api)


def jpeg(size=(1200, 800), **save) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, (30, 120, 200)).save(out, "JPEG", **save)
    return out.getvalue()


def upload(api, csrf, raw, name="photo.jpg", alt="College building", **form):
    data = {"altText": alt, **form} if alt is not None else dict(form)
    return api.post(
        URL,
        files={"file": (name, raw, "application/octet-stream")},
        data=data,
        headers=changes(csrf),
    )


def actions(db, name):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == name)))


# ---- uploading photos ----


def test_a_photo_becomes_resized_webp_copies_and_a_private_original(api, staff, dirs, db_session):
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"
    exif[0x0112] = 6  # the camera was held sideways
    exif.get_ifd(0x8825).update({1: "N", 2: (13.0, 4.0, 5.0), 3: "E", 4: (80.0, 1.0, 2.0)})
    raw = jpeg((1800, 1200), exif=exif.tobytes())
    response = upload(
        api, staff, raw, name="C:\\Users\\Asha\\DSC_0042.JPG", alt="Front of the college"
    )
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["kind"] == "image" and body["mime"] == "image/webp"
    # turned upright (1200 x 1800); sizes are by width, so nothing is scaled up
    assert (body["width"], body["height"]) == (1200, 1800)
    assert [v["width"] for v in body["variants"]] == [400, 800, 1200]
    assert body["originalFilename"] == "DSC_0042.JPG"  # no folders from the person's computer
    assert body["altText"] == "Front of the college" and body["cropBottom"] is False
    assert body["thumbUrl"] == body["variants"][0]["url"]
    assert str(dirs.uploads) not in api.get(URL).text  # no folders of the server in any answer

    names = dirs.served()
    assert len(names) == len(body["variants"]) and all(
        __import__("re").fullmatch(TOKEN_FILE, n) for n in names
    )
    assert body["url"] == body["variants"][-1]["url"]  # the largest copy is the main file
    for variant in body["variants"]:
        path = dirs.uploads / variant["url"].rsplit("/", 1)[1]
        assert stat.S_IMODE(path.stat().st_mode) == 0o644  # the web server must be able to read it
        with Image.open(path) as img:
            assert img.format == "WEBP" and img.width == variant["width"]
            assert len(img.getexif()) == 0
        assert b"SecretCamera" not in path.read_bytes()

    (original,) = dirs.private()  # the original is kept, in a different, private place
    saved = dirs.originals / original
    assert saved.read_bytes() == raw and stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert original not in dirs.served()

    row = db_session.get(Media, body["id"])
    assert (
        row.stored_name == body["variants"][-1]["url"].rsplit("/", 1)[1]
        and row.uploaded_by is not None
    )
    assert len(actions(db_session, "media_upload")) == 1


def test_small_pictures_are_not_enlarged(api, staff):
    body = upload(api, staff, jpeg((300, 200))).json()
    assert [v["width"] for v in body["variants"]] == [300] and body["width"] == 300


def test_the_date_stamp_crop_flag_is_stored(api, staff):
    body = upload(api, staff, jpeg((300, 200)), cropBottom="true").json()
    assert body["cropBottom"] is True


def test_the_file_name_is_cleaned_and_never_used_on_disk(api, staff, dirs):
    body = upload(api, staff, jpeg((300, 200)), name="../../etc/pass\u202ewd\x00.jpg").json()
    assert "/" not in body["originalFilename"] and "\u202e" not in body["originalFilename"]
    assert all("passwd" not in n and ".." not in n for n in dirs.served())


# ---- uploading PDFs ----


def test_a_pdf_is_stored_as_it_is(api, staff, dirs):
    response = upload(api, staff, PDF, name="syllabus.pdf", alt=None)
    assert response.status_code == 201
    body = response.json()
    assert body["kind"] == "pdf" and body["mime"] == "application/pdf" and body["width"] is None
    assert (
        body["url"].endswith(".pdf") and body["variants"] == [] and body["thumbUrl"] == body["url"]
    )
    assert (dirs.uploads / body["url"].rsplit("/", 1)[1]).read_bytes() == PDF
    assert dirs.private() == []  # PDFs are not copied twice


def test_a_pdf_may_have_a_title(api, staff):
    assert upload(api, staff, PDF, alt="Syllabus 2026").json()["altText"] == "Syllabus 2026"


def test_a_pdf_with_scripts_is_refused(api, staff, dirs):
    evil = PDF.replace(b"%%EOF", b"/JavaScript (app.alert(1)) %%EOF")
    response = upload(api, staff, evil, name="x.pdf", alt=None)
    assert response.status_code == 422 and response.json()["code"] == "invalid_file"
    assert dirs.served() == []


# ---- alt text ----


@pytest.mark.parametrize("alt", [None, "", "   ", "x" * 301, "bad\x00text", "left\u202eright"])
def test_a_photo_needs_proper_alt_text(api, staff, dirs, db_session, alt):
    response = upload(api, staff, jpeg((300, 200)), alt=alt)
    assert response.status_code == 422 and response.json()["code"] == "invalid_alt_text"
    assert dirs.served() == [] and dirs.private() == []  # nothing saved
    assert db_session.scalars(select(Media)).all() == []


# ---- refused files ----


@pytest.mark.parametrize(
    ("raw", "name"),
    [
        (b"GIF89a" + b"\x00" * 30, "x.gif"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "x.svg"),
        (b"<html><script>alert(1)</script></html>", "photo.jpg"),
        (b"MZ\x90\x00" + b"\x00" * 50, "photo.png"),
        (b"", "empty.jpg"),
        (b"just some text", "notes.txt"),
    ],
)
def test_other_kinds_of_files_are_refused_whatever_they_are_called(api, staff, dirs, raw, name):
    response = upload(api, staff, raw, name=name)
    assert response.status_code == 415 and response.json()["code"] == "unsupported_type"
    assert dirs.served() == []


def test_the_files_type_comes_from_its_content_not_its_name(api, staff):
    assert upload(api, staff, jpeg((300, 200)), name="really-a-photo.pdf").json()["kind"] == "image"


@pytest.mark.parametrize(
    "raw",
    [jpeg()[:200], b"\xff\xd8\xff" + b"garbage" * 30],
)
def test_broken_pictures_are_refused_and_leave_nothing_behind(api, staff, dirs, raw):
    response = upload(api, staff, raw)
    assert response.status_code == 422 and response.json()["code"] == "invalid_file"
    assert dirs.served() == [] and dirs.private() == []


def test_huge_pictures_are_refused(api, staff):
    out = io.BytesIO()
    Image.new("RGB", (7000, 10)).save(out, "PNG")
    response = upload(api, staff, out.getvalue(), name="wide.png")
    assert response.status_code == 422 and "too large" in response.json()["detail"]


def test_files_over_the_limit_are_refused(api, staff, dirs):
    just_over = b"%PDF-" + b"0" * (1024 * 1024) + b"\n%%EOF"  # 1 MB + a little
    response = upload(api, staff, just_over, name="big.pdf", alt=None)
    assert response.status_code == 413 and response.json()["code"] == "file_too_large"
    way_over = b"%PDF-" + b"0" * (1024 * 1024 + 200_000) + b"\n%%EOF"  # stopped before it is read
    response = upload(api, staff, way_over, name="huge.pdf", alt=None)
    assert response.status_code == 413 and response.json()["code"] == "file_too_large"
    assert dirs.served() == []


def test_a_failure_while_saving_leaves_no_files_behind(db_session, dirs, monkeypatch):
    storage = media_service.Storage(dirs.uploads, dirs.originals)

    def broken(*_):
        raise RuntimeError("database went away")

    monkeypatch.setattr(db_session, "flush", broken)
    with pytest.raises(RuntimeError):
        media_service.save_upload(
            db_session,
            storage,
            raw=jpeg(),
            filename="a.jpg",
            alt_text="a",
            crop_bottom=False,
            user_id=None,
        )
    assert dirs.served() == [] and dirs.private() == []


# ---- who may upload ----


def test_uploading_needs_a_signed_in_member_of_staff_with_the_token(api, make_user):
    raw = jpeg((300, 200))
    assert upload(api, "x", raw).status_code == 401
    make_user()
    csrf = signed_in(api)
    no_token = api.post(
        URL,
        files={"file": ("a.jpg", raw)},
        data={"altText": "x"},
        headers={"Origin": "http://localhost"},
    )
    assert no_token.status_code == 403
    elsewhere = api.post(
        URL,
        files={"file": ("a.jpg", raw)},
        data={"altText": "x"},
        headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"},
    )
    assert elsewhere.status_code == 403
    assert upload(api, csrf, raw).status_code == 201


def test_there_is_a_limit_on_uploads_per_hour(api, staff, db_session):
    me = api.get("/api/v1/auth/me").json()["user"]["id"]
    db_session.add_all(
        AuditLog(user_id=me, action="media_upload")
        for _ in range(media_service.MAX_UPLOADS_PER_HOUR)
    )
    db_session.flush()
    response = upload(api, staff, jpeg((300, 200)))
    assert response.status_code == 429 and response.json()["code"] == "too_many_uploads"


# ---- listing ----


def test_the_list_is_newest_first_and_can_be_filtered_and_paged(api, staff):
    first = upload(api, staff, jpeg((300, 200)), name="campus-front.jpg", alt="Front view").json()
    second = upload(api, staff, PDF, name="Syllabus_BSc.pdf", alt=None).json()
    third = upload(
        api, staff, jpeg((300, 200)), name="x.jpg", alt="NSS volunteers 100% keen"
    ).json()

    listed = api.get(URL).json()
    assert [m["id"] for m in listed] == [third["id"], second["id"], first["id"]]
    assert [m["id"] for m in api.get(URL, params={"kind": "pdf"}).json()] == [second["id"]]
    assert [m["id"] for m in api.get(URL, params={"q": "CAMPUS"}).json()] == [first["id"]]  # name
    assert [m["id"] for m in api.get(URL, params={"q": "volunteers"}).json()] == [
        third["id"]
    ]  # alt
    assert [m["id"] for m in api.get(URL, params={"q": "100%"}).json()] == [third["id"]]
    assert api.get(URL, params={"q": "Fr%nt"}).json() == []  # "%" is not a wildcard
    assert api.get(URL, params={"q": "S_llabus"}).json() == []  # nor is "_"
    assert [m["id"] for m in api.get(URL, params={"q": "Syllabus_BSc"}).json()] == [second["id"]]
    page = api.get(URL, params={"limit": 2}).json()
    assert [m["id"] for m in page] == [third["id"], second["id"]]
    rest = api.get(URL, params={"limit": 2, "before_id": page[-1]["id"]}).json()
    assert [m["id"] for m in rest] == [first["id"]]


@pytest.mark.parametrize(
    "query", ["limit=0", "limit=101", "before_id=0", "kind=video", "q=" + "x" * 101]
)
def test_list_filters_are_validated(api, staff, query):
    assert api.get(f"{URL}?{query}").status_code == 422


def test_one_item_and_unknown_ids(api, staff):
    made = upload(api, staff, jpeg((300, 200))).json()
    assert api.get(f"{URL}/{made['id']}").json() == made
    for path in (f"{URL}/999999999", f"{URL}/999999999/usage"):
        assert api.get(path).status_code == 404
    assert api.get(f"{URL}/abc").status_code == 422


def test_the_library_needs_a_session(api):
    assert api.get(URL).status_code == 401


# ---- editing ----


def test_alt_text_and_crop_can_be_changed_and_the_website_is_refreshed(
    api, staff, db_session, refreshes
):
    made = upload(api, staff, jpeg((300, 200))).json()
    response = api.patch(
        f"{URL}/{made['id']}",
        json={"altText": "The new description", "cropBottom": True},
        headers=changes(staff),
    )
    assert response.status_code == 200
    assert (
        response.json()["altText"] == "The new description"
        and response.json()["cropBottom"] is True
    )
    assert refreshes == [revalidate.ALL_TAGS]
    entry = actions(db_session, "media_update")[0]
    assert entry.changes == {"fields": ["altText", "cropBottom"]} and entry.entity_id == made["id"]


def test_edits_are_validated_and_protected(api, staff, refreshes):
    made = upload(api, staff, jpeg((300, 200))).json()
    path = f"{URL}/{made['id']}"
    assert api.patch(path, json={}, headers=changes(staff)).status_code == 422
    assert api.patch(path, json={"altText": "x" * 301}, headers=changes(staff)).status_code == 422
    assert api.patch(path, json={"filename": "x"}, headers=changes(staff)).status_code == 422
    assert (
        api.patch(path, json={"altText": "ok"}, headers={"Origin": "http://localhost"}).status_code
        == 403
    )
    assert (
        api.patch(f"{URL}/999999", json={"altText": "ok"}, headers=changes(staff)).status_code
        == 404
    )
    assert refreshes == []


# ---- deleting ----


def test_an_unused_file_is_deleted_with_all_its_copies(api, staff, dirs, db_session):
    made = upload(api, staff, jpeg((1800, 1200))).json()
    assert dirs.served() and dirs.private()
    response = api.delete(f"{URL}/{made['id']}", headers=changes(staff))
    assert response.status_code == 204
    assert dirs.served() == [] and dirs.private() == []
    assert db_session.get(Media, made["id"]) is None
    assert len(actions(db_session, "media_delete")) == 1
    assert api.delete(f"{URL}/{made['id']}", headers=changes(staff)).status_code == 404


def test_deleting_needs_the_token(api, staff, dirs):
    made = upload(api, staff, jpeg((300, 200))).json()
    assert (
        api.delete(f"{URL}/{made['id']}", headers={"Origin": "http://localhost"}).status_code == 403
    )
    assert dirs.served()


def make_uses(db, media_id: int) -> dict[str, object]:
    """One use of the photo in every place a photo can be used."""
    department = Department(name="Computer Science", slug="cs")
    db.add(department)
    db.flush()
    page = Page(key="about", title="About", slug="about")
    page.sections.append(
        PageSection(
            type="two_column",
            position=0,
            data={
                "main": [{"type": "image", "data": {"media": {"mediaId": media_id}}}],
                "aside": [],
            },
        )
    )
    news = News(
        title="Open day",
        slug="open-day",
        category="event",
        summary="s",
        body={"type": "doc", "content": []},
        published_at=time.strftime("%Y-%m-%d"),
    )
    activity = Activity(title="Camp", slug="camp", group="nss", summary="s")
    activity.photos.append(ActivityPhoto(media_id=media_id))
    news.attachments.append(NewsAttachment(media_id=media_id, label="Circular"))
    db.add_all([page, news, activity])
    db.add(SiteSetting(key="brand", value={"logo": {"mediaId": media_id}}))
    db.add(GalleryItem(kind="photo", media_id=media_id))
    db.add(
        Course(
            department_id=department.id,
            name="B.Sc",
            tab="B.Sc",
            slug="bsc",
            duration_years=3,
            summary="s",
            syllabus_media_id=media_id,
        )
    )
    db.add(
        Faculty(
            department_id=department.id,
            name="A",
            designation="d",
            qualification="q",
            photo_media_id=media_id,
        )
    )
    db.flush()
    return {"page": page, "news": news, "activity": activity}


def test_a_file_that_is_used_cannot_be_deleted(api, staff, dirs, db_session):
    made = upload(api, staff, jpeg((300, 200))).json()
    make_uses(db_session, made["id"])
    page = db_session.scalars(select(Page)).one()
    page.og_media_id = made["id"]
    db_session.flush()

    response = api.delete(f"{URL}/{made['id']}", headers=changes(staff))
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "media_in_use"
    entities = sorted(u["entity"] for u in body["usages"])
    assert entities == sorted(
        [
            "page",  # share image
            "page_section",  # a photo inside the "two columns" section
            "settings",  # the logo
            "course",
            "faculty",
            "news",  # an attachment
            "activity",
            "gallery_item",
        ]
    )
    assert all(u["label"] and u["id"] for u in body["usages"])
    assert dirs.served() and dirs.private() and db_session.get(Media, made["id"])  # nothing lost

    shown = api.get(f"{URL}/{made['id']}/usage").json()["usages"]
    assert sorted(u["entity"] for u in shown) == entities


def test_each_kind_of_use_blocks_deletion_on_its_own(api, staff, db_session):
    # the photo is used in exactly one place at a time; each must block the delete
    made = upload(api, staff, jpeg((300, 200))).json()
    media_id = made["id"]
    department = Department(name="D", slug="d")
    db_session.add(department)
    db_session.flush()
    news = News(
        title="N",
        slug="n",
        category="event",
        summary="s",
        body={"type": "doc", "content": []},
        published_at=time.strftime("%Y-%m-%d"),
    )
    page = Page(key="home", title="Home", slug="")
    activity = Activity(title="A", slug="a", group="nss", summary="s")
    db_session.add_all([news, page, activity])
    db_session.flush()
    uses = [
        lambda: setattr(page, "og_media_id", media_id),
        lambda: setattr(news, "cover_media_id", media_id),
        lambda: setattr(activity, "cover_media_id", media_id),
        lambda: db_session.add(
            Course(
                department_id=department.id,
                name="C",
                tab="C",
                slug="c",
                duration_years=3,
                summary="s",
                cover_media_id=media_id,
            )
        ),
        lambda: db_session.add(SiteSetting(key="seo", value={"ogImage": {"mediaId": media_id}})),
    ]
    undo = [
        lambda: setattr(page, "og_media_id", None),
        lambda: setattr(news, "cover_media_id", None),
        lambda: setattr(activity, "cover_media_id", None),
        lambda: db_session.execute(Course.__table__.delete()),
        lambda: db_session.execute(SiteSetting.__table__.delete()),
    ]
    for use, remove in zip(uses, undo, strict=True):
        use()
        db_session.flush()
        blocked = api.delete(f"{URL}/{media_id}", headers=changes(staff))
        assert blocked.status_code == 409, blocked.text
        remove()
        db_session.flush()
    assert api.get(f"{URL}/{media_id}/usage").json() == {"usages": []}
    assert api.delete(f"{URL}/{media_id}", headers=changes(staff)).status_code == 204


def test_another_photos_pointer_does_not_block_deletion(api, staff, db_session):
    made = upload(api, staff, jpeg((300, 200))).json()
    page = Page(key="home", title="Home", slug="")
    page.sections.append(
        PageSection(type="quote", position=0, data={"image": {"mediaId": made["id"] + 1}})
    )
    db_session.add(page)
    db_session.flush()
    assert api.delete(f"{URL}/{made['id']}", headers=changes(staff)).status_code == 204


def test_deleting_never_touches_files_outside_the_upload_folders(db_session, dirs, tmp_path):
    outside = tmp_path / "precious.txt"
    outside.write_text("keep me")
    row = Media(
        kind="image",
        original_filename="x",
        stored_name="../precious.txt",
        mime="image/webp",
        size_bytes=1,
        width=1,
        height=1,
        variants=[{"width": 1, "name": "../precious.txt"}, {"width": 2, "name": "/etc/hostname"}],
    )
    storage = media_service.Storage(dirs.uploads, dirs.originals)
    paths = media_service.files_of(storage, row)
    assert all(path.parent in (dirs.uploads, dirs.originals) for path in paths)
    assert outside not in paths and Path("/etc/hostname") not in paths


# ---- maintenance ----


def old(path: Path, seconds=7200) -> None:
    moment = time.time() - seconds
    os.utime(path, (moment, moment))


def test_cleanup_removes_only_old_unreferenced_files(api, staff, dirs, db_session):
    made = upload(api, staff, jpeg((1200, 800))).json()
    keep_served, keep_private = dirs.served(), dirs.private()
    dirs.uploads.joinpath("leftover-from-a-crash.webp").write_bytes(b"x")
    dirs.uploads.joinpath("half-written.webp.tmp").write_bytes(b"x")
    dirs.originals.joinpath("abandoned").write_bytes(b"x")
    dirs.uploads.joinpath("being-uploaded-right-now.webp").write_bytes(b"x")
    for name in ("leftover-from-a-crash.webp", "half-written.webp.tmp"):
        old(dirs.uploads / name)
    old(dirs.originals / "abandoned")
    for name in keep_served:  # even old files that belong to a library entry stay
        old(dirs.uploads / name)

    storage = media_service.Storage(dirs.uploads, dirs.originals)
    assert [p.name for p in media_service.cleanup_orphans(db_session, storage, dry_run=True)] == [
        "half-written.webp.tmp",
        "leftover-from-a-crash.webp",
        "abandoned",
    ]
    assert len(dirs.served()) == len(keep_served) + 3  # a dry run deletes nothing
    removed = media_service.cleanup_orphans(db_session, storage)
    assert len(removed) == 3
    assert dirs.served() == sorted(keep_served + ["being-uploaded-right-now.webp"])
    assert dirs.private() == keep_private
    assert db_session.get(Media, made["id"])


def test_reprocessing_makes_copies_for_photos_that_lack_them(db_session, dirs):
    dirs.uploads.mkdir(parents=True)
    (dirs.uploads / "seed-old.jpg").write_bytes(jpeg((1156, 868)))
    row = Media(
        kind="image",
        original_filename="old.jpg",
        stored_name="seed-old.jpg",
        mime="image/jpeg",
        size_bytes=1,
        width=1156,
        height=868,
    )
    pdf = Media(
        kind="pdf",
        original_filename="a.pdf",
        stored_name="a.pdf",
        mime="application/pdf",
        size_bytes=1,
    )
    missing = Media(
        kind="image",
        original_filename="gone.jpg",
        stored_name="seed-gone.jpg",
        mime="image/jpeg",
        size_bytes=1,
        width=1,
        height=1,
    )
    storage = media_service.Storage(dirs.uploads, None)
    assert media_service.reprocess_media(row, storage) is True
    assert [v["width"] for v in row.variants] == [400, 800, 1156]
    assert all((dirs.uploads / v["name"]).is_file() for v in row.variants)
    assert row.stored_name == "seed-old.jpg" and (row.width, row.height) == (1156, 868)  # unchanged
    assert media_service.reprocess_media(pdf, storage) is False
    assert media_service.reprocess_media(missing, storage) is False


# ---- the "refresh the website" message ----

SETTINGS = get_settings()


def refresh_settings(**changes):
    from pydantic import SecretStr

    values = {
        "revalidate_url": "http://frontend:3000/internal/revalidate",
        "revalidate_secret": SecretStr("s" * 32),
        **changes,
    }
    return SETTINGS.model_copy(update=values)


def test_the_website_is_told_which_pages_to_refresh():
    import httpx

    seen = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"ok": True})

    assert revalidate.notify(
        refresh_settings(), ["news", "pages"], transport=httpx.MockTransport(answer)
    )
    request = seen[0]
    assert request.method == "POST" and request.url == "http://frontend:3000/internal/revalidate"
    assert request.headers["x-revalidate-secret"] == "s" * 32
    assert request.read() == b'{"tags":["news","pages"]}'


def test_a_website_that_does_not_answer_never_breaks_the_save(caplog):
    import logging

    import httpx

    logging.getLogger("app").addHandler(caplog.handler)
    try:
        for transport in (
            httpx.MockTransport(lambda r: httpx.Response(401)),
            httpx.MockTransport(lambda r: httpx.Response(500)),
            httpx.MockTransport(lambda r: (_ for _ in ()).throw(httpx.ConnectError("refused"))),
        ):
            assert revalidate.notify(refresh_settings(), ["news"], transport=transport) is False
    finally:
        logging.getLogger("app").removeHandler(caplog.handler)
    assert "could not be told" in caplog.text
    assert "s" * 32 not in caplog.text and "frontend:3000" not in caplog.text


def test_nothing_is_sent_when_the_hook_is_not_configured():
    import httpx

    def fail(request):
        raise AssertionError("no request expected")

    transport = httpx.MockTransport(fail)
    assert (
        revalidate.notify(refresh_settings(revalidate_url=""), ["news"], transport=transport)
        is False
    )
    assert (
        revalidate.notify(refresh_settings(revalidate_secret=None), ["news"], transport=transport)
        is False
    )
