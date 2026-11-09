"""Staff endpoints for the gallery, departments, courses and faculty, and who may do what."""

import pytest
from sqlalchemy import select

from app.models import Course, Department, Media, Redirect


@pytest.fixture
def photos(seeded) -> list[int]:
    return [
        m.id for m in seeded.scalars(select(Media).where(Media.kind == "image").order_by(Media.id))
    ]


@pytest.fixture
def pdf(seeded) -> int:
    row = Media(
        kind="pdf",
        original_filename="syllabus.pdf",
        stored_name="syllabus-test.pdf",
        mime="application/pdf",
        size_bytes=10,
    )
    seeded.add(row)
    seeded.flush()
    return row.id


@pytest.fixture
def department(seeded) -> Department:
    return seeded.scalars(select(Department).order_by(Department.id)).first()


def course(department_id: int, **changes) -> dict:
    return {
        "departmentId": department_id,
        "name": "B.Sc Physics",
        "tab": "Physics",
        "durationYears": 3,
        "summary": "Mechanics, optics and modern physics.",
        **changes,
    }


def member(department_id: int, **changes) -> dict:
    return {
        "departmentId": department_id,
        "name": "Dr. Test Teacher",
        "designation": "Lecturer",
        "qualification": "M.Sc, Ph.D",
        **changes,
    }


# ============================ gallery ============================


def test_gallery_photos_and_videos(editor, seeded, photos, refreshes):
    photo = editor.post(
        "/gallery", {"mediaId": photos[0], "category": "nss", "caption": "Camp day"}
    )
    assert photo.status_code == 201, photo.text
    assert photo.json()["media"]["id"] == photos[0] and photo.json()["isPublished"] is True
    video = editor.post(
        "/gallery", {"kind": "video", "youtubeId": "dQw4w9WgXcQ", "category": "campus"}
    )
    assert video.status_code == 201 and video.json()["media"] is None
    assert refreshes == [["gallery"], ["gallery"]]


@pytest.mark.parametrize(
    "bad",
    [
        {},  # a photo needs a photo
        {"kind": "video"},  # a video needs a YouTube id
        {"kind": "video", "youtubeId": "dQw4w9WgXcQ", "mediaId": 1},  # not both
        {"mediaId": 1, "youtubeId": "dQw4w9WgXcQ"},
        {"kind": "video", "youtubeId": "bad id!"},
        {"kind": "video", "youtubeId": "<script>alert(1)</script>"},
        {"mediaId": 987654321},
        {"mediaId": 1, "category": "party"},
        {"mediaId": 1, "caption": "x" * 201},
    ],
)
def test_invalid_gallery_items_are_refused(editor, seeded, photos, bad):
    if bad.get("mediaId") == 1:
        bad = {**bad, "mediaId": photos[0]}
    assert editor.post("/gallery", bad).status_code == 422


def test_a_pdf_cannot_be_a_gallery_photo(editor, seeded, pdf):
    response = editor.post("/gallery", {"mediaId": pdf})
    assert response.status_code == 422 and response.json()["code"] == "wrong_media_type"


def test_gallery_update_delete_list_and_order(editor, seeded, photos, refreshes):
    ids = [
        editor.post("/gallery", {"mediaId": photos[n], "category": "leo"}).json()["id"]
        for n in range(3)
    ]
    assert editor.post("/gallery/reorder", {"ids": [ids[2], ids[1], ids[0]]}).status_code == 204
    leo = [g["id"] for g in editor.get("/gallery", category="leo").json()]
    assert [i for i in leo if i in ids] == [ids[2], ids[1], ids[0]]
    changed = editor.put(
        f"/gallery/{ids[0]}", {"mediaId": photos[5], "caption": "New", "isPublished": False}
    )
    assert changed.json()["caption"] == "New" and changed.json()["isPublished"] is False
    public_ids = [g["id"] for g in editor.api.get("/api/v1/public/gallery").json()]
    assert ids[0] not in public_ids and ids[1] in public_ids  # unpublished items stay hidden
    assert editor.delete(f"/gallery/{ids[1]}").status_code == 204
    assert editor.get(f"/gallery/{ids[1]}").status_code == 404
    assert editor.get("/gallery/999999999").status_code == 404
    assert editor.post("/gallery/reorder", {"ids": [ids[0], 987654321]}).status_code == 422
    assert db_has_photo(editor, photos[1])  # deleting a gallery entry never deletes the photo


def db_has_photo(editor, media_id: int) -> bool:
    return editor.api.get(f"/api/v1/admin/media/{media_id}").status_code == 200


# ============================ departments ============================


def test_editors_can_edit_departments_but_not_create_or_delete_them(
    editor, boss, seeded, department
):
    assert editor.post("/departments", {"name": "Physics"}).status_code == 403
    changed = editor.put(
        f"/departments/{department.id}",
        {"name": "Computer Science and IT", "description": "Programming."},
    )
    assert changed.status_code == 200 and changed.json()["name"] == "Computer Science and IT"
    assert changed.json()["slug"] == department.slug  # kept
    assert editor.delete(f"/departments/{department.id}").status_code == 403
    assert len(editor.get("/departments").json()) == 3


def test_super_admins_create_and_delete_departments(boss, seeded, refreshes):
    made = boss.post("/departments", {"name": "Physics Department"})
    assert made.status_code == 201 and made.json()["slug"] == "physics-department"
    assert refreshes[-1] == ["courses", "faculty"]  # both show department names
    assert (
        boss.post("/departments", {"name": "Other", "slug": "physics-department"}).status_code
        == 409
    )
    assert boss.delete(f"/departments/{made.json()['id']}").status_code == 204
    assert boss.get(f"/departments/{made.json()['id']}").status_code == 404


def test_a_department_with_courses_or_people_cannot_be_deleted(boss, seeded, department):
    in_use = boss.delete(f"/departments/{department.id}")
    assert in_use.status_code == 409 and in_use.json()["code"] == "department_in_use"
    assert "course" in in_use.json()["detail"]


def test_departments_can_be_reordered(editor, seeded):
    ids = [d["id"] for d in editor.get("/departments").json()]
    assert editor.post("/departments/reorder", {"ids": ids[::-1]}).status_code == 204
    assert [d["id"] for d in editor.get("/departments").json()] == ids[::-1]


# ============================ courses ============================


def test_super_admins_create_courses_and_editors_edit_them(
    editor, boss, seeded, department, photos, pdf
):
    made = boss.post(
        "/courses",
        course(
            department.id,
            syllabusMediaId=pdf,
            coverMediaId=photos[0],
            subjects=["Mechanics", "Optics"],
            eligibility="Intermediate (MPC)",
            seats="60",
            fees="As per university norms",
        ),
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["slug"] == "b-sc-physics" or body["slug"].startswith("b-sc-physics")
    assert body["departmentName"] == department.name and body["syllabus"]["kind"] == "pdf"
    assert body["subjects"] == ["Mechanics", "Optics"]
    assert "b-sc-physics" in [c["slug"] for c in editor.api.get("/api/v1/public/courses").json()]

    edited = editor.put(
        f"/courses/{body['id']}",
        course(department.id, name="B.Sc Physics (Honours)", seats="40", isPublished=False),
    )
    assert edited.status_code == 200 and edited.json()["seats"] == "40"
    assert body["slug"] not in [c["slug"] for c in editor.api.get("/api/v1/public/courses").json()]
    assert editor.post("/courses", course(department.id)).status_code == 403
    assert editor.delete(f"/courses/{body['id']}").status_code == 403
    assert boss.delete(f"/courses/{body['id']}").status_code == 204


@pytest.mark.parametrize(
    "bad",
    [
        {"durationYears": 0},
        {"durationYears": 7},
        {"durationYears": "3"},
        {"name": ""},
        {"summary": "x" * 401},
        {"subjects": ["x"] * 41},
        {"syllabusMediaId": 987654321},
        {"description": {"type": "doc", "content": [{"type": "iframe"}]}},
    ],
)
def test_invalid_courses_are_refused(boss, seeded, department, bad):
    assert boss.post("/courses", course(department.id, **bad)).status_code == 422


def test_course_references_are_checked(boss, seeded, department, photos, pdf):
    assert boss.post("/courses", course(987654321)).status_code == 404  # no such department
    syllabus_is_photo = boss.post("/courses", course(department.id, syllabusMediaId=photos[0]))
    assert (
        syllabus_is_photo.status_code == 422
        and syllabus_is_photo.json()["code"] == "wrong_media_type"
    )
    cover_is_pdf = boss.post("/courses", course(department.id, coverMediaId=pdf))
    assert cover_is_pdf.status_code == 422


def test_renaming_a_published_course_address_leaves_a_redirect(editor, seeded, db_session):
    existing = db_session.scalars(select(Course).order_by(Course.id)).first()
    old = existing.slug
    payload = course(
        existing.department_id, name=existing.name, tab=existing.tab, slug="renamed-course"
    )
    assert editor.put(f"/courses/{existing.id}", payload).status_code == 200
    redirect = db_session.scalars(select(Redirect)).one()
    assert (redirect.from_path, redirect.to_path) == (f"/courses/{old}", "/courses/renamed-course")
    public = editor.api.get("/api/v1/public/redirects").json()
    assert {
        "fromPath": f"/courses/{old}",
        "toPath": "/courses/renamed-course",
        "statusCode": 301,
    } in public


def test_courses_can_be_reordered_and_listed(editor, seeded):
    ids = [c["id"] for c in editor.get("/courses").json()]
    assert len(ids) == 3
    assert editor.post("/courses/reorder", {"ids": ids[::-1]}).status_code == 204
    assert [c["id"] for c in editor.get("/courses").json()] == ids[::-1]
    assert editor.get("/courses/999999999").status_code == 404


# ============================ faculty ============================


def test_editors_manage_faculty(editor, seeded, department, photos, pdf, refreshes):
    made = editor.post(
        "/faculty", member(department.id, photoMediaId=photos[0], bio="Teaches physics.")
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["departmentName"] == department.name and body["photo"]["id"] == photos[0]
    assert refreshes == [["faculty"]]
    assert body["id"] in [m["id"] for m in editor.api.get("/api/v1/public/faculty").json()]

    hidden = editor.put(f"/faculty/{body['id']}", member(department.id, isActive=False))
    assert hidden.json()["isActive"] is False
    assert body["id"] not in [m["id"] for m in editor.api.get("/api/v1/public/faculty").json()]
    assert body["id"] in [m["id"] for m in editor.get("/faculty").json()]  # staff still see it
    assert editor.delete(f"/faculty/{body['id']}").status_code == 204
    assert editor.get(f"/faculty/{body['id']}").status_code == 404


@pytest.mark.parametrize(
    "bad",
    [
        {"name": ""},
        {"bio": "x" * 1001},
        {"photoMediaId": 987654321},
        {"sortOrder": -1},
        {"isActive": "maybe"},
    ],
)
def test_invalid_faculty_are_refused(editor, seeded, department, bad):
    assert editor.post("/faculty", member(department.id, **bad)).status_code == 422


def test_faculty_references_and_order(editor, seeded, department, pdf):
    assert editor.post("/faculty", member(987654321)).status_code == 404
    assert editor.post("/faculty", member(department.id, photoMediaId=pdf)).status_code == 422
    ids = [m["id"] for m in editor.get("/faculty").json()]
    assert editor.post("/faculty/reorder", {"ids": ids[::-1]}).status_code == 204
    assert [m["id"] for m in editor.get("/faculty").json()] == ids[::-1]
    assert [m["id"] for m in editor.get("/faculty", limit=2).json()] == ids[::-1][:2]


def test_audit_log_records_changes_without_their_content(editor, boss, seeded, department):
    editor.post("/faculty", member(department.id, name="Secret Name Person"))
    entries = boss.get("/audit-log", limit=20).json()
    created = next(e for e in entries if e["action"] == "faculty_create")
    assert created["entity"] == "faculty" and created["entityId"] and created["ip"]
    assert "Secret Name Person" not in str(entries)
