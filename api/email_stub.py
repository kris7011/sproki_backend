# api/email_stub.py
# pyright: reportMissingImports=none, reportUndefinedVariable=none

import sys
from .settings import settings


def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    parts: list[str] = []
    parts.append("=" * 60)
    parts.append(f"[MAIL STUB] From: {settings.email_from} → To: {to}")
    parts.append(f"Subject: {subject}")
    parts.append("Text:")
    parts.append(text)
    if html is not None:
        parts.append("")
        parts.append("HTML:")
        parts.append(html)
    parts.append("=" * 60)
    sys.stdout.write("\n".join(parts) + "\n")
