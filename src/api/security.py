"""JWT issuing / verification for the API.

A single token type carries the principal's role plus any role-scoped ids
(``club_id`` for coaches, ``tournament_id`` for referees).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

_SECRET_KEY = os.environ.get(
    "JUDO_SECRET_KEY", "dev-secret-change-me-in-production-please-32+"
)
_ALGORITHM = "HS256"
_TOKEN_TTL = timedelta(hours=12)


@dataclass
class Principal:
    """The authenticated entity behind a request."""

    role: str  # "admin" | "coach" | "referee"
    user_id: str | None = None
    club_id: str | None = None
    tournament_id: str | None = None
    display_name: str = ""


def create_token(principal: Principal) -> str:
    """Encode a ``Principal`` into a signed JWT."""
    now = datetime.now(timezone.utc)
    payload = {
        "role": principal.role,
        "user_id": principal.user_id,
        "club_id": principal.club_id,
        "tournament_id": principal.tournament_id,
        "display_name": principal.display_name,
        "iat": now,
        "exp": now + _TOKEN_TTL,
    }
    return jwt.encode(payload, _SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str) -> Principal:
    """Decode a JWT into a ``Principal``. Raises ``jwt.PyJWTError`` on failure."""
    data = jwt.decode(token, _SECRET_KEY, algorithms=[_ALGORITHM])
    return Principal(
        role=data["role"],
        user_id=data.get("user_id"),
        club_id=data.get("club_id"),
        tournament_id=data.get("tournament_id"),
        display_name=data.get("display_name", ""),
    )
