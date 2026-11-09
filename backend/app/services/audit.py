"""Who did what, when, from where. Append-only. Never put passwords, tokens or personal data in
`changes`; record ids and the names of fields that changed."""

from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    db: Session,
    action: str,
    *,
    user_id: int | None = None,
    entity: str | None = None,
    entity_id: int | None = None,
    changes: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Adds an entry. The caller commits, so it is saved together with the change it describes."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            changes=changes,
            ip=ip[:45] if ip else None,
        )
    )


def recent_user_count(db: Session, action: str, user_id: int, *, seconds: int) -> int:
    """How many times this person did `action` in the last `seconds` seconds."""
    since = func.now() - text(f"interval '{int(seconds)} seconds'")
    stmt = select(func.count()).where(
        AuditLog.action == action, AuditLog.user_id == user_id, AuditLog.created_at >= since
    )
    return db.scalar(stmt) or 0


def recent_count(db: Session, action: str, ip: str, *, seconds: int) -> int:
    """How many times `action` was recorded for this address in the last `seconds` seconds."""
    since = func.now() - text(f"interval '{int(seconds)} seconds'")
    stmt = select(func.count()).where(
        AuditLog.action == action, AuditLog.ip == ip[:45], AuditLog.created_at >= since
    )
    return db.scalar(stmt) or 0
