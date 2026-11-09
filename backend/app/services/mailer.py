import logging
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid

from app.core.config import Settings

log = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 10


def _new_message(settings: Settings, to: str, subject: str, body: str) -> EmailMessage:
    """A plain-text message. Values only ever go into the body, never into the headers the visitor
    could influence, which prevents header injection."""
    mail = EmailMessage()
    mail["Subject"] = subject
    mail["From"] = settings.mail_from
    mail["To"] = to
    # Mail servers and spam filters expect these two; the library does not add them.
    mail["Date"] = format_datetime(datetime.now(UTC))
    domain = settings.mail_from.rpartition("@")[2].strip("> ") or None
    mail["Message-ID"] = make_msgid(domain=domain)
    mail.set_content(body)
    return mail


def deliver(settings: Settings, mail: EmailMessage) -> None:
    """Sends one message through the configured mail server. Raises if anything goes wrong, so the
    caller decides what to do (the website logs it; the test command shows it)."""
    host, port = settings.smtp_host, settings.smtp_port
    context = ssl.create_default_context()  # checks the server's certificate
    if settings.smtp_security == "ssl":
        client = smtplib.SMTP_SSL(host, port, timeout=_TIMEOUT_SECONDS, context=context)
    else:
        client = smtplib.SMTP(host, port, timeout=_TIMEOUT_SECONDS)
    with client as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        # (the settings refuse a password without encryption, so this never sends it in clear)
        if settings.smtp_user and settings.smtp_password:
            smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
        smtp.send_message(mail)


def send_enquiry_email(
    settings: Settings,
    *,
    name: str,
    phone: str,
    course: str | None,
    message: str | None,
    source_page: str | None,
) -> None:
    """Email a new enquiry to the college. Runs after the response, so it never slows the visitor.

    The enquiry is already saved in the database, so a failure here is logged and not raised.
    """
    if not settings.email_enabled:
        log.info("Enquiry email skipped: SMTP is not configured")
        return

    mail = _new_message(
        settings,
        settings.enquiry_to_email,
        "New website enquiry",
        "A new enquiry was sent from the college website.\n\n"
        f"Name: {name}\n"
        f"Phone: {phone}\n"
        f"Course: {course or '-'}\n"
        f"Page: {source_page or '-'}\n\n"
        f"Message:\n{message or '-'}\n",
    )
    try:
        deliver(settings, mail)
    except Exception:
        log.exception("Enquiry email could not be sent")


def send_test_email(settings: Settings, to: str) -> None:
    """A test message for the `send-test-email` command. Raises on any problem."""
    mail = _new_message(
        settings,
        to,
        "Test email from the college website",
        "This is a test from the VRR Degree College website.\n\n"
        "If you can read it, the mail settings are correct and new enquiries will arrive here.\n",
    )
    deliver(settings, mail)
