"""Which kinds of content have a history, and how to put an old version back.
Each resource registers itself here (see the admin_*.py routers)."""

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.services.auth import Auth

# entity name -> function(db, auth, entity_id, saved_data) that restores that version
Restorer = Callable[[Session, Auth, int, dict[str, Any]], int]
RESTORERS: dict[str, Restorer] = {}


def restorer(entity: str) -> Callable[[Restorer], Restorer]:
    def register(function: Restorer) -> Restorer:
        RESTORERS[entity] = function
        return function

    return register
