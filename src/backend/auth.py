"""Password hashing and verification (stdlib-only, no extra deps)."""

import hashlib
import secrets

_ITERATIONS = 260_000


def hash_password(password: str) -> str:
    """Return ``salt:hex_hash`` using PBKDF2-SHA256."""
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return f"{salt}:{h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check *password* against a ``salt:hex_hash`` string."""
    salt, expected = stored.split(":", 1)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ITERATIONS)
    return secrets.compare_digest(h.hex(), expected)


def generate_referee_token() -> str:
    """Return a URL-safe random token for referee access."""
    return secrets.token_urlsafe(16)
