import hashlib
import secrets

import bcrypt


def generate_secret_token() -> str:
    """High-entropy opaque token, shown to the caller exactly once (device API
    keys, refresh tokens) — only its hash is ever persisted."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Deterministic hash used as the lookup key for opaque tokens. The token
    itself is high-entropy random data (not a user password), so a salted KDF
    like bcrypt isn't needed here."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
