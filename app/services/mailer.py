# === FILE: app/services/mailer.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class MailMessage:
    to: str
    subject: str
    html: str


class Mailer:
    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or "console"

    def send(self, msg: MailMessage):
        # Replace with SendGrid/Mailgun/SMTP; for now print to console for visibility
        print(
            f"[MAIL->{self.provider}] to={msg.to} subject={msg.subject}\n{msg.html}"
        )


mailer = Mailer()
