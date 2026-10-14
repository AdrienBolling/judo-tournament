"""FastAPI dependencies: DB session + auth guards."""

from __future__ import annotations

from collections.abc import Iterator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from backend.database.database import get_session

from .security import Principal, decode_token

_bearer = HTTPBearer(auto_error=False)


def db_session() -> Iterator[Session]:
    """Yield a request-scoped database session."""
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def current_principal(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    """Decode the bearer token into a ``Principal`` or raise 401."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_roles(*roles: str):
    """Build a dependency that allows only the given roles."""

    def _guard(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(roles)}",
            )
        return principal

    return _guard
