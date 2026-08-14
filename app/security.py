import hashlib
import secrets


def generate_secret_token() -> str:
    """High-entropy opaque token, shown to the caller exactly once (device API
    keys, refresh tokens) — only its hash is ever persisted."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Deterministic hash used as the lookup key for opaque tokens. The token
    itself is high-entropy random data (not a user password), so a salted KDF
    like bcrypt isn't needed here."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
