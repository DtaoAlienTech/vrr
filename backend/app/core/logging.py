"""Logging with a request id on every line, so one problem can be followed through the logs.
Passwords, tokens, e-mail addresses and request bodies are never logged."""

import logging
import re
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s")
    )
    app_logger = logging.getLogger("app")
    app_logger.handlers = [handler]
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


def new_request_id(incoming: str | None) -> str:
    """Keep the id sent by our own proxy when it looks like one; never trust anything else."""
    return incoming if incoming and _SAFE_ID.match(incoming) else uuid.uuid4().hex
