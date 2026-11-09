"""Walks EVERY staff route and checks the protection, so a new endpoint cannot forget it:
signed-out visitors are refused, changes need the CSRF token, and exactly the intended routes
are for super admins only."""

import re

import pytest

from app.main import app

METHODS = ("get", "post", "put", "patch", "delete")
UNSAFE = {"post", "put", "patch", "delete"}

# (method, path pattern) of every route that only a super admin may use
SUPER_ADMIN_ONLY = {
    ("get", "/api/v1/admin/users"),
    ("post", "/api/v1/admin/users"),
    ("put", "/api/v1/admin/users/{user_id}"),
    ("post", "/api/v1/admin/users/{user_id}/reset-password"),
    ("post", "/api/v1/admin/users/{user_id}/reset-two-factor"),
    ("get", "/api/v1/admin/audit-log"),
    ("get", "/api/v1/admin/settings"),
    ("get", "/api/v1/admin/settings/schema"),
    ("put", "/api/v1/admin/settings/{group}"),
    ("post", "/api/v1/admin/departments"),
    ("delete", "/api/v1/admin/departments/{department_id}"),
    ("post", "/api/v1/admin/courses"),
    ("delete", "/api/v1/admin/courses/{course_id}"),
}


def admin_routes() -> list[tuple[str, str]]:
    routes = []
    for path, operations in app.openapi()["paths"].items():
        if path.startswith("/api/v1/admin"):
            routes += [(method, path) for method in operations if method in METHODS]
    return sorted(routes)


def url(path: str) -> str:
    return re.sub(
        r"\{[^}]+\}", "1", path
    )  # an id that does not exist is fine: protection comes first


ROUTES = admin_routes()


def test_the_walk_really_finds_the_staff_routes():
    paths = {path for _, path in ROUTES}
    assert len(ROUTES) >= 60
    for expected in (
        "/api/v1/admin/news",
        "/api/v1/admin/media",
        "/api/v1/admin/pages/{page_id}/sections",
        "/api/v1/admin/settings/{group}",
        "/api/v1/admin/users",
        "/api/v1/admin/revisions/{revision_id}/restore",
        "/api/v1/admin/enquiries/export.csv",
        "/api/v1/admin/redirects",
    ):
        assert expected in paths
    assert set(ROUTES) >= SUPER_ADMIN_ONLY  # no stale entries in the list above


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_signed_out_visitors_are_refused(api, method, path):
    response = getattr(api, method)(url(path), headers={"Origin": "http://localhost"})
    assert response.status_code == 401, f"{method.upper()} {path} answered {response.status_code}"
    assert response.json()["code"] == "not_authenticated"


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if r[0] in UNSAFE])
def test_changes_without_the_csrf_token_are_refused(editor, method, path):
    response = getattr(editor.api, method)(url(path), headers={"Origin": "http://localhost"})
    assert response.status_code == 403 and response.json()["code"] == "csrf_failed", (
        f"{method} {path}"
    )


@pytest.mark.parametrize(("method", "path"), [r for r in ROUTES if r[0] in UNSAFE])
def test_changes_from_another_website_are_refused(editor, method, path):
    headers = {"Origin": "https://evil.example", "X-CSRF-Token": editor.csrf}
    response = getattr(editor.api, method)(url(path), headers=headers)
    assert response.status_code == 403 and response.json()["code"] == "bad_origin", (
        f"{method} {path}"
    )


@pytest.mark.parametrize(("method", "path"), ROUTES)
def test_editors_reach_exactly_the_routes_meant_for_them(editor, method, path):
    headers = {"Origin": "http://localhost", "X-CSRF-Token": editor.csrf}
    response = getattr(editor.api, method)(url(path), headers=headers)
    if (method, path) in SUPER_ADMIN_ONLY:
        assert response.status_code == 403 and response.json()["code"] == "forbidden", (
            f"{method} {path}"
        )
    else:
        assert response.status_code not in (401, 403), (
            f"{method.upper()} {path}: {response.status_code}"
        )


def test_a_super_admin_without_two_factor_is_locked_out_of_every_staff_route(api, make_user):
    from tests.helpers import signed_in

    make_user("newboss@example.org", role="super_admin")
    signed_in(api, email="newboss@example.org")
    blocked = [
        path
        for method, path in ROUTES
        if method == "get" and "{" not in path and "export" not in path
    ]
    for path in blocked:
        response = api.get(url(path))
        assert response.status_code == 403 and response.json()["code"] == "totp_setup_required", (
            path
        )
