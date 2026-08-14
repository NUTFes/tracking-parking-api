"""Google ID token verification + NUTFes executive-committee email format
enforcement, shared by admin login (app/usecases/auth_usecase.py, which also
checks an allow-list) and the general-user dependency (app/deps.py, which
trusts any correctly-formatted account — no allow-list, no session of ours).

Calling code must reference this module's function via `google_auth.
verify_google_id_token(...)` (not `from ... import verify_google_id_token`)
so tests can monkeypatch it — see tests/conftest.py."""
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


def verify_google_id_token(raw_token: str) -> str:
    """Verifies signature/audience/expiry against Google, then enforces the
    NUTFes email format. Returns the verified, lower-cased email address.
    Raises UnauthorizedError on any failure (invalid token, unverified email,
    or an email that doesn't match the executive-committee format)."""
    try:
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
