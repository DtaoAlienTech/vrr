import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import Settings

log = logging.getLogger(__name__)


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
    Values go only into the plain-text body (never into headers), which prevents header injection.
    """
    if not settings.email_enabled:
        log.info("Enquiry email skipped: SMTP is not configured")
        return

    mail = EmailMessage()
    mail["Subject"] = "New website enquiry"
    mail["From"] = settings.mail_from
    mail["To"] = settings.enquiry_to_email
    mail.set_content(
        "A new enquiry was sent from the college website.\n\n"
        f"Name: {name}\n"
        f"Phone: {phone}\n"
        f"Course: {course or '-'}\n"
        f"Page: {source_page or '-'}\n\n"
        f"Message:\n{message or '-'}\n"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if settings.smtp_user and settings.smtp_password:
                smtp.login(settings.smtp_user, settings.smtp_password.get_secret_value())
            smtp.send_message(mail)
    except Exception:
        log.exception("Enquiry email could not be sent")
