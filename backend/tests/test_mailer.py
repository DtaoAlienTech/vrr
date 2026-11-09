"""Enquiry emails: what is sent, how it is protected, and that a failure never loses an enquiry.

The wire tests talk real SMTP to the local test mailbox (app/devtools/mail_sink.py)."""

import logging
import socket

import pytest
from pydantic import ValidationError

from app import cli
from app.core.config import Settings
from app.devtools.mail_sink import MailSink
from app.services import mailer

OFFICE = "office@example.org"
SENDER = "Website <website@example.org>"


@pytest.fixture
def sink():
    server = MailSink()
    server.serve_in_background()
    yield server
    server.shutdown()
    server.server_close()


def settings_for(port: int, **changes) -> Settings:
    values = {
        "smtp_host": "127.0.0.1",
        "smtp_port": port,
        "smtp_security": "none",
        "enquiry_to_email": OFFICE,
        "mail_from": SENDER,
        **changes,
    }
    return Settings(**values)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def send(settings: Settings, **changes) -> None:
    values = {
        "name": "Asha Reddy",
        "phone": "9876543210",
        "course": "B.Sc Zoology",
        "message": "Is hostel available?",
        "source_page": "/admissions",
        **changes,
    }
    mailer.send_enquiry_email(settings, **values)


# ============================ real SMTP conversation ============================


def test_an_enquiry_arrives_with_everything_in_it(sink):
    send(settings_for(sink.port))
    assert len(sink.messages) == 1
    mail = sink.messages[0]
    assert mail["Subject"] == "New website enquiry"
    assert mail["To"] == OFFICE and mail["From"] == SENDER
    body = mail.get_content()
    for line in [
        "Name: Asha Reddy",
        "Phone: 9876543210",
        "Course: B.Sc Zoology",
        "Page: /admissions",
        "Is hostel available?",
    ]:
        assert line in body
    assert sink.envelopes[0] == ("website@example.org", [OFFICE])


def test_the_message_has_a_date_and_an_id_so_mail_filters_trust_it(sink):
    send(settings_for(sink.port))
    mail = sink.messages[0]
    assert mail["Date"] and mail["Message-ID"].endswith("@example.org>")


def test_empty_optional_values_show_a_dash(sink):
    send(settings_for(sink.port), course=None, message=None, source_page=None)
    body = sink.messages[0].get_content().replace("\r\n", "\n")  # SMTP lines end in CRLF
    assert "Course: -" in body and "Page: -" in body and "Message:\n-" in body


def test_what_a_visitor_types_can_never_become_a_header(sink):
    attack = "Eve\r\nBcc: evil@example.org\r\nSubject: hacked"
    send(settings_for(sink.port), name=attack, message="x\r\n.\r\nQUIT\r\nMAIL FROM:<a@b.c>")
    assert len(sink.messages) == 1
    mail = sink.messages[0]
    assert mail["Bcc"] is None and mail["Subject"] == "New website enquiry"
    assert sink.envelopes[0][1] == [OFFICE]  # nobody else got a copy
    assert "Bcc: evil@example.org" in mail.get_content()  # it is only text in the body


def test_a_special_character_name_arrives_intact(sink):
    send(settings_for(sink.port), name="Śrīnivāsa Rao ✓", message="தமிழ் 日本語")
    body = sink.messages[0].get_content()
    assert "Śrīnivāsa Rao ✓" in body and "தமிழ் 日本語" in body


# ============================ encryption and login ============================


class Recorder:
    """Stands in for smtplib.SMTP / SMTP_SSL and writes down what the mailer did."""

    log: list[tuple]

    def __init__(self, kind: str, log: list[tuple]):
        self.kind, self.log = kind, log

    def __call__(self, host, port, timeout=None, context=None):
        self.log.append(("connect", self.kind, host, port, timeout))
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.log.append(("close",))

    def starttls(self, context=None):
        assert context is not None and context.verify_mode.name == "CERT_REQUIRED"
        self.log.append(("starttls",))

    def login(self, user, password):
        self.log.append(("login", user, password))

    def send_message(self, mail):
        self.log.append(("send", mail["To"]))


@pytest.fixture
def conversation(monkeypatch):
    log: list[tuple] = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", Recorder("plain", log))
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", Recorder("ssl", log))
    return log


def real_login(**changes) -> Settings:
    return settings_for(
        587,
        smtp_host="smtp.example.org",
        smtp_user="office",
        smtp_password="app-password",
        **changes,
    )


def test_starttls_encrypts_before_the_password_is_sent(conversation):
    send(real_login(smtp_security="starttls"))
    assert conversation == [
        ("connect", "plain", "smtp.example.org", 587, 10),
        ("starttls",),
        ("login", "office", "app-password"),
        ("send", OFFICE),
        ("close",),
    ]


def test_ssl_mode_is_encrypted_from_the_first_byte(conversation):
    send(real_login(smtp_security="ssl", smtp_port=465))
    assert conversation == [
        ("connect", "ssl", "smtp.example.org", 465, 10),
        ("login", "office", "app-password"),
        ("send", OFFICE),
        ("close",),
    ]


def test_without_a_login_none_is_sent_and_nothing_is_asked(conversation):
    send(settings_for(587, smtp_host="smtp.example.org", smtp_security="starttls"))
    assert [step[0] for step in conversation] == ["connect", "starttls", "send", "close"]


def test_a_password_is_never_sent_without_encryption():
    with pytest.raises(ValidationError, match="never sends a password"):
        Settings(smtp_security="none", smtp_user="office", smtp_password="secret")
    with pytest.raises(ValidationError):
        Settings(smtp_security="none", smtp_password="secret")


def test_an_unknown_security_mode_is_refused():
    with pytest.raises(ValidationError):
        Settings(smtp_security="maybe")


def test_the_password_is_not_shown_when_settings_are_printed():
    text = repr(real_login(smtp_security="starttls"))
    assert "app-password" not in text


# ============================ when it cannot be sent ============================


def test_without_mail_settings_nothing_is_attempted(conversation):
    send(Settings(smtp_host="", enquiry_to_email="", mail_from=""))
    assert conversation == []


def test_a_mail_server_that_is_down_never_breaks_the_enquiry(caplog):
    settings = settings_for(free_port())
    with caplog.at_level(logging.ERROR):
        send(settings)  # must not raise: the enquiry is already saved
    assert "Enquiry email could not be sent" in caplog.text
    with pytest.raises(OSError):
        mailer.deliver(settings, mailer._new_message(settings, OFFICE, "s", "b"))


def test_a_hostile_address_cannot_inject_headers_into_the_test_mail(sink):
    settings = settings_for(sink.port)
    with pytest.raises(ValueError):
        mailer.send_test_email(settings, "a@b.co\r\nBcc: evil@example.org")
    assert sink.messages == []


# ============================ the test command ============================


def run_command(monkeypatch, capsys, settings: Settings, to: str | None = None):
    monkeypatch.setattr(cli, "get_settings", lambda: settings)
    code = cli.send_test_mail(to=to)
    return code, capsys.readouterr().out


def test_the_test_command_sends_and_says_so(sink, monkeypatch, capsys):
    code, out = run_command(monkeypatch, capsys, settings_for(sink.port))
    assert code == 0 and "Sent." in out and OFFICE in out
    assert sink.messages[0]["Subject"] == "Test email from the college website"
    assert "app-password" not in out


def test_the_test_command_can_send_to_another_address(sink, monkeypatch, capsys):
    code, _ = run_command(monkeypatch, capsys, settings_for(sink.port), to="principal@example.org")
    assert code == 0 and sink.messages[0]["To"] == "principal@example.org"


def test_the_test_command_names_what_is_missing(monkeypatch, capsys):
    code, out = run_command(
        monkeypatch, capsys, Settings(smtp_host="", mail_from="", enquiry_to_email="")
    )
    assert code == 1
    assert "SMTP_HOST" in out and "MAIL_FROM" in out and "ENQUIRY_TO_EMAIL" in out


def test_the_test_command_refuses_something_that_is_not_an_address(monkeypatch, capsys):
    code, out = run_command(monkeypatch, capsys, settings_for(1), to="not-an-address")
    assert code == 1 and "not an email address" in out


def test_the_test_command_explains_a_server_that_cannot_be_reached(monkeypatch, capsys):
    code, out = run_command(monkeypatch, capsys, settings_for(free_port()))
    assert code == 1 and "FAILED" in out and "SMTP_HOST and SMTP_PORT" in out


def test_the_test_command_explains_a_wrong_encryption_setting(sink, monkeypatch, capsys):
    code, out = run_command(monkeypatch, capsys, settings_for(sink.port, smtp_security="starttls"))
    assert code == 1 and "FAILED" in out and "SMTP_SECURITY" in out


# ============================ the test mailbox itself ============================


def talk(port: int, lines: list[bytes]) -> list[bytes]:
    answers: list[bytes] = []
    with socket.create_connection(("127.0.0.1", port), timeout=5) as client:
        reader = client.makefile("rb")
        answers.append(reader.readline())
        for line in lines:
            client.sendall(line)
            if not line.endswith(b"\r\n.\r\n") and not line.startswith(b"."):
                answers.append(reader.readline())
        client.sendall(b"QUIT\r\n")
    return answers


def test_the_mailbox_answers_nonsense_politely_and_keeps_working(sink):
    answers = talk(sink.port, [b"HELLO?\r\n", b"DATA\r\n", b"RCPT TO:<a@b.co>\r\n", b"NOOP\r\n"])
    assert answers[1].startswith(b"500") and answers[2].startswith(b"503")
    assert answers[3].startswith(b"250") and answers[4].startswith(b"250")
    assert talk(sink.port, [b"NOOP\r\n"])[0].startswith(b"220")


def test_the_mailbox_refuses_a_huge_message_and_stays_up(sink):
    huge = b"Subject: big\r\n\r\n" + b"x" * 100 + b"\r\n"
    with socket.create_connection(("127.0.0.1", sink.port), timeout=10) as client:
        reader = client.makefile("rb")
        reader.readline()
        for command in (b"MAIL FROM:<a@b.co>\r\n", b"RCPT TO:<c@d.co>\r\n", b"DATA\r\n"):
            client.sendall(command)
            reader.readline()
        for _ in range(12_000):
            client.sendall(huge)
        client.sendall(b".\r\n")
        assert reader.readline().startswith(b"552")
    assert sink.messages == []
    assert talk(sink.port, [b"NOOP\r\n"])[1].startswith(b"250")


def test_the_mailbox_does_not_pretend_to_support_login_or_tls(sink):
    answers = talk(sink.port, [b"AUTH PLAIN abc\r\n", b"STARTTLS\r\n"])
    assert answers[1].startswith(b"502") and answers[2].startswith(b"502")
