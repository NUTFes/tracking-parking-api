"""Google ID token verification + NUTFes executive-committee email format
enforcement, shared by admin login (app/usecases/auth_usecase.py, which also
checks an allow-list) and the general-user dependency (app/deps.py, which
trusts any correctly-formatted account — no allow-list, no session of ours).

Calling code must reference this module's function via `google_auth.
verify_google_id_token(...)` (not `from ... import verify_google_id_token`)
so tests can monkeypatch it — see tests/conftest.py."""
import base64
import json
import re

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings
from app.exceptions import UnauthorizedError

# e.g. "25.m.kitano.nutfes@gmail.com" -> label "25.m.kitano" (2-digit class
# year, 1-letter given-name initial, surname). This is the NUTFes executive
# committee's Google Workspace naming convention.
NUTFES_EMAIL_PATTERN = re.compile(r"^(?P<label>\d{2}\.[a-zA-Z]\.[a-zA-Z]+)\.nutfes@gmail\.com$")

_google_request = google_requests.Request()


def _decode_unverified_payload(raw_token: str) -> dict:
    """E2E test-mode only (settings.google_auth_test_mode) — decodes a JWT's
    payload segment WITHOUT checking its signature, audience, or expiry.
    Real Google Sign-In can't be scripted end-to-end, so Playwright signs its
    own throwaway tokens instead; this is the matching relaxed decode path.
    Never reachable unless google_auth_test_mode is explicitly enabled."""
    try:
        _header, payload_b64, _signature = raw_token.split(".")
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"malformed test-mode token: {exc}") from exc


def verify_google_id_token(raw_token: str) -> str:
    """Verifies signature/audience/expiry against Google, then enforces the
    NUTFes email format. Returns the verified, lower-cased email address.
    Raises UnauthorizedError on any failure (invalid token, unverified email,
    or an email that doesn't match the executive-committee format)."""
    try:
        if settings.google_auth_test_mode:
            payload = _decode_unverified_payload(raw_token)
        else:
            payload = google_id_token.verify_oauth2_token(raw_token, _google_request, settings.google_client_id)
    except ValueError as exc:
        raise UnauthorizedError(f"invalid Google ID token: {exc}") from exc

    email = (payload.get("email") or "").lower()
    if not email or not payload.get("email_verified"):
        raise UnauthorizedError("Google account email is missing or unverified")

    if not NUTFES_EMAIL_PATTERN.match(email):
        raise UnauthorizedError("メールアドレスの形式が実行委員の規則に合致しません")

    return email


def label_from_email(email: str) -> str:
    """"25.m.kitano.nutfes@gmail.com" -> "25.m.kitano". Assumes email already
    passed NUTFES_EMAIL_PATTERN (e.g. via verify_google_id_token)."""
    match = NUTFES_EMAIL_PATTERN.match(email)
    if match is None:
        raise ValueError(f"email does not match the NUTFes format: {email}")
    return match.group("label")
