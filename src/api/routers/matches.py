"""Match scoring and group standings."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.database import crud
from backend.database.models import Group, Match
from backend.scoring import compute_group_standings, determine_match_winner, is_instant_win

from .. import schemas
from ..deps import current_principal, db_session
from ..security import Principal
from ..serializers import match_read, participant_name_map

router = APIRouter(tags=["matches"])

_VALID_SIDES = {"a", "b"}
_VALID_POINTS = {"ippon", "wazari", "yuko"}


def _group_or_404(session: Session, group_id: uuid.UUID) -> Group:
    group = crud.get_by_id(session, Group, group_id)
    if not group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")
    return group


def _assert_scoring_access(principal: Principal, group: Group) -> None:
    """Referees may only touch groups in their own tournament; admins anything."""
    if principal.role == "admin":
        return
    if principal.role == "referee" and principal.tournament_id == str(group.tournament_id):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed to score this group")


def _match_or_404(session: Session, match_id: uuid.UUID) -> Match:
    match = crud.get_by_id(session, Match, match_id)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Match not found")
    return match


@router.get("/groups/{group_id}/matches", response_model=list[schemas.MatchRead])
def list_matches(
    group_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[schemas.MatchRead]:
    group = _group_or_404(session, group_id)
    _assert_scoring_access(principal, group)
    names = participant_name_map(session, group.tournament_id)
    return [match_read(m, names) for m in crud.get_matches_by_group(session, group_id)]


@router.get("/groups/{group_id}/standings", response_model=list[schemas.StandingRow])
def standings(
    group_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[schemas.StandingRow]:
    group = _group_or_404(session, group_id)
    _assert_scoring_access(principal, group)
    names = participant_name_map(session, group.tournament_id)
    rows = compute_group_standings(crud.get_matches_by_group(session, group_id))
    return [
        schemas.StandingRow(name=names.get(r["participant_id"], "?"), **r) for r in rows
    ]


@router.post("/matches/{match_id}/score", response_model=schemas.MatchRead)
def add_score(
    match_id: uuid.UUID,
    body: schemas.ScoreAction,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> schemas.MatchRead:
    match = _match_or_404(session, match_id)
    group = _group_or_404(session, match.group_id)
    _assert_scoring_access(principal, group)
    if match.completed:
        raise HTTPException(status.HTTP_409_CONFLICT, "Match is already completed")
    if body.side not in _VALID_SIDES or body.point not in _VALID_POINTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid side or point")

    field = f"score_{body.side}_{body.point}"
    setattr(match, field, getattr(match, field) + 1)
    # Ippon or 2 waza-ari ends the bout immediately.
    if is_instant_win(match):
        match.winner_id = determine_match_winner(match)
        match.completed = True
    return _save(session, match, group)


@router.post("/matches/{match_id}/end", response_model=schemas.MatchRead)
def end_match(
    match_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> schemas.MatchRead:
    match = _match_or_404(session, match_id)
    group = _group_or_404(session, match.group_id)
    _assert_scoring_access(principal, group)
    match.winner_id = determine_match_winner(match)
    match.completed = True
    return _save(session, match, group)


@router.post("/matches/{match_id}/reset", response_model=schemas.MatchRead)
def reset_match(
    match_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> schemas.MatchRead:
    match = _match_or_404(session, match_id)
    group = _group_or_404(session, match.group_id)
    _assert_scoring_access(principal, group)
    match.score_a_ippon = match.score_a_wazari = match.score_a_yuko = 0
    match.score_b_ippon = match.score_b_wazari = match.score_b_yuko = 0
    match.winner_id = None
    match.completed = False
    return _save(session, match, group)


def _save(session: Session, match: Match, group: Group) -> schemas.MatchRead:
    session.add(match)
    session.commit()
    session.refresh(match)
    names = participant_name_map(session, group.tournament_id)
    return match_read(match, names)
