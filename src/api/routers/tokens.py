"""Referee access tokens for a tournament."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.auth import generate_referee_token
from backend.database import crud
from backend.database.models import RefereeToken, Tournament

from .. import schemas
from ..deps import db_session, require_roles
from ..security import Principal

router = APIRouter(tags=["referee-tokens"])


@router.get(
    "/tournaments/{tournament_id}/tokens", response_model=list[schemas.RefereeTokenRead]
)
def list_tokens(
    tournament_id: uuid.UUID,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> list[RefereeToken]:
    return crud.get_referee_tokens_by_tournament(session, tournament_id)


_VALID_ROLES = {"referee", "inscription"}


@router.post(
    "/tournaments/{tournament_id}/tokens",
    response_model=schemas.RefereeTokenRead,
    status_code=status.HTTP_201_CREATED,
)
def create_token(
    tournament_id: uuid.UUID,
    body: schemas.TokenCreate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> RefereeToken:
    if not crud.get_by_id(session, Tournament, tournament_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tournament not found")
    if not body.label:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Label is required")
    role = body.role if body.role in _VALID_ROLES else "referee"
    token_value = (body.token or "").strip() or generate_referee_token()
    if crud.get_referee_token_by_value(session, token_value):
        raise HTTPException(status.HTTP_409_CONFLICT, "That token value is already in use")
    return crud.create(
        session,
        RefereeToken(
            token=token_value,
            label=body.label,
            tournament_id=tournament_id,
            role=role,
        ),
    )


@router.put(
    "/tournaments/{tournament_id}/tokens/{token_id}",
    response_model=schemas.RefereeTokenRead,
)
def update_token(
    tournament_id: uuid.UUID,
    token_id: uuid.UUID,
    body: schemas.TokenUpdate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> RefereeToken:
    token = crud.get_by_id(session, RefereeToken, token_id)
    if token is None or token.tournament_id != tournament_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")

    changes: dict = {}
    if body.token is not None:
        new_value = body.token.strip()
        if not new_value:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Token cannot be empty")
        existing = crud.get_referee_token_by_value(session, new_value)
        if existing and existing.id != token.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "That token value is already in use")
        changes["token"] = new_value
    if body.label is not None:
        if not body.label.strip():
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Label cannot be empty")
        changes["label"] = body.label.strip()

    return crud.update(session, token, **changes) if changes else token
