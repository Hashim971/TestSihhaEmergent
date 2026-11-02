"""Emergent managed transactional email. Bodies come only from server-side templates."""
import ipaddress
import logging
import os
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ["EMERGENT_EMAIL_KEY"]
EMAIL_FROM_NAME = os.environ["EMAIL_FROM_NAME"]
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str | None:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if EMAIL_REPLY_TO:
        payload["contact_email"] = EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                     headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        try:
            code = e.response.json().get("code", "")
        except ValueError:
            code = ""
        if code in ("insufficient_credits", "integration_disabled", "daily_limit_reached"):
            logger.warning("Email paused: %s (%s)", code, e.response.status_code)
            raise HTTPException(status_code=503, detail="Email is temporarily unavailable")
        logger.error("Email send failed: %s %s", e.response.status_code, e.response.text)
        raise HTTPException(status_code=502, detail="Failed to send email")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Email send error: %s", e)
        raise HTTPException(status_code=500, detail="Failed to send email")


def account_invite_email(name: str, account_name: str, link: str) -> tuple[str, str]:
    subject = f"You've been invited to {account_name} on {EMAIL_FROM_NAME}"
    brand = escape(EMAIL_FROM_NAME)
    html = (
        '<table role="presentation" width="100%" style="background:#F6F1E7"><tr><td style="padding:32px">'
        '<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;background:#ffffff;'
        'border-radius:16px"><tr><td style="padding:32px;font-family:Arial,sans-serif;color:#1F2A24">'
        f'<p style="font-size:20px;font-weight:bold;color:#1F4D3A;margin:0 0 16px">{brand}</p>'
        f'<p style="margin:0 0 12px">Hi {escape(name)},</p>'
        f'<p style="margin:0 0 20px">{escape(account_name)} has added you to their workspace. '
        'Set your password to get started. This link works once and expires in 7 days.</p>'
        f'<p style="margin:0 0 24px"><a href="{escape(link, quote=True)}" style="background:#1F4D3A;color:#ffffff;'
        'padding:12px 24px;border-radius:999px;text-decoration:none;font-weight:bold">Set my password</a></p>'
        "<p style=\"margin:0 0 8px;font-size:13px;color:#5B6B62\">If you weren't expecting this, you can ignore "
        'this email.</p>'
        f'<p style="margin:16px 0 0;font-size:12px;color:#8A968F">Sent by {brand}. We never ask for your password '
        'or card details by email.</p>'
        '</td></tr></table></td></tr></table>'
    )
    return subject, html


def password_reset_email(name: str, link: str) -> tuple[str, str]:
    subject = f"Reset your {EMAIL_FROM_NAME} password"
    brand = escape(EMAIL_FROM_NAME)
    html = (
        '<table role="presentation" width="100%" style="background:#F6F1E7"><tr><td style="padding:32px">'
        '<table role="presentation" width="100%" style="max-width:520px;margin:0 auto;background:#ffffff;'
        'border-radius:16px"><tr><td style="padding:32px;font-family:Arial,sans-serif;color:#1F2A24">'
        f'<p style="font-size:20px;font-weight:bold;color:#1F4D3A;margin:0 0 16px">{brand}</p>'
        f'<p style="margin:0 0 12px">Hi {escape(name)},</p>'
        '<p style="margin:0 0 20px">We received a request to reset the password for your account. '
        'This link works once and expires in 1 hour.</p>'
        f'<p style="margin:0 0 24px"><a href="{escape(link, quote=True)}" style="background:#1F4D3A;color:#ffffff;'
        'padding:12px 24px;border-radius:999px;text-decoration:none;font-weight:bold">Choose a new password</a></p>'
        "<p style=\"margin:0 0 8px;font-size:13px;color:#5B6B62\">If you didn't ask for this, you can ignore "
        'this email — your password stays the same.</p>'
        f'<p style="margin:16px 0 0;font-size:12px;color:#8A968F">Sent by {brand}. We never ask for your password '
        'or card details by email.</p>'
        '</td></tr></table></td></tr></table>'
    )
    return subject, html
