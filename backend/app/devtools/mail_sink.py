"""A tiny test mailbox: accepts email on a local port and prints it, instead of sending it.

For trying the enquiry emails without a real mail account:

    docker compose --profile mail up -d mailcatcher
    (in .env: SMTP_HOST=mailcatcher  SMTP_PORT=1025  SMTP_SECURITY=none
              ENQUIRY_TO_EMAIL=office@example.org  MAIL_FROM=website@example.org)
    docker compose logs -f mailcatcher

It speaks just enough SMTP for that. There is no encryption and no login, so it is for the test
network only and must never be exposed to the internet. Standard library only.
"""

import contextlib
import re
import socketserver
import sys
import threading
from email import message_from_bytes, policy
from email.message import EmailMessage
from typing import cast

_ADDRESS = re.compile(r"<([^<>]*)>")


def address_in(command: str) -> str:
    """The address of "MAIL FROM:<a@b.co> SIZE=5" -> "a@b.co"."""
    found = _ADDRESS.search(command)
    return found.group(1) if found else command.partition(":")[2].strip()


MAX_MESSAGE_BYTES = 1_000_000
MAX_LINE_BYTES = 4_096
TIMEOUT_SECONDS = 15


class _Session(socketserver.StreamRequestHandler):
    server: "MailSink"

    def setup(self) -> None:
        super().setup()
        self.connection.settimeout(TIMEOUT_SECONDS)

    def reply(self, text: str) -> None:
        self.wfile.write(text.encode("ascii", "replace") + b"\r\n")
        self.wfile.flush()

    def read_message(self) -> bytes | None:
        """Everything up to the lone "." line. None if it is too big."""
        data = bytearray()
        too_big = False
        while True:
            line = self.rfile.readline(MAX_LINE_BYTES + 1)
            if not line:
                return None
            if line in (b".\r\n", b".\n"):
                return None if too_big else bytes(data)
            if line.startswith(b".."):
                line = line[1:]  # un-escape a line that started with "."
            data += line
            if len(data) > MAX_MESSAGE_BYTES:
                too_big = True
                data.clear()

    def handle(self) -> None:
        self.reply("220 mail-sink ready (test mailbox, nothing is delivered)")
        sender, recipients = "", []
        try:
            while True:
                raw = self.rfile.readline(MAX_LINE_BYTES + 1)
                if not raw or len(raw) > MAX_LINE_BYTES:
                    return
                line = raw.decode("ascii", "replace").strip()
                word = line.split(" ", 1)[0].upper()
                if word in ("EHLO", "HELO"):
                    self.reply("250-mail-sink")
                    self.reply(f"250 SIZE {MAX_MESSAGE_BYTES}")
                elif word == "MAIL":
                    sender, recipients = address_in(line), []
                    self.reply("250 OK")
                elif word == "RCPT":
                    recipients.append(address_in(line))
                    self.reply("250 OK")
                elif word == "DATA":
                    if not recipients:
                        self.reply("503 need a recipient first")
                        continue
                    self.reply("354 end with a line holding only a dot")
                    body = self.read_message()
                    if body is None:
                        self.reply("552 message too big")
                        continue
                    self.server.accept(sender, recipients, body)
                    sender, recipients = "", []
                    self.reply("250 OK message kept")
                elif word == "RSET":
                    sender, recipients = "", []
                    self.reply("250 OK")
                elif word == "NOOP":
                    self.reply("250 OK")
                elif word == "QUIT":
                    self.reply("221 bye")
                    return
                elif word in ("STARTTLS", "AUTH"):
                    self.reply("502 not supported: use SMTP_SECURITY=none without a login")
                else:
                    self.reply("500 unknown command")
        except (TimeoutError, ConnectionError, OSError):
            return


class MailSink(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, address: tuple[str, int] = ("127.0.0.1", 0), *, echo: bool = False):
        super().__init__(address, _Session)
        self.echo = echo
        self.messages: list[EmailMessage] = []
        self.envelopes: list[tuple[str, list[str]]] = []
        self._lock = threading.Lock()

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    def accept(self, sender: str, recipients: list[str], body: bytes) -> None:
        message = cast(EmailMessage, message_from_bytes(body, policy=policy.default))
        with self._lock:
            self.messages.append(message)
            self.envelopes.append((sender, recipients))
        if self.echo:
            print(
                f"\n=== email received ===\nenvelope from: {sender}\nenvelope to:   "
                f"{', '.join(recipients)}\n{body.decode('utf-8', 'replace')}=== end ===",
                flush=True,
            )

    def serve_in_background(self) -> threading.Thread:
        thread = threading.Thread(
            target=lambda: self.serve_forever(poll_interval=0.02), daemon=True
        )
        thread.start()
        return thread


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 1025
    with MailSink(("0.0.0.0", port), echo=True) as sink:  # noqa: S104 (test network only)
        print(f"Test mailbox listening on port {port}. Emails are printed here.", flush=True)
        with contextlib.suppress(KeyboardInterrupt):
            sink.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
