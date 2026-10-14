"""Helpers converting ORM rows into API response schemas."""

from __future__ import annotations

import uuid

from sqlmodel import Session

from backend.database import crud
from backend.database.models import Group, Match, Member, Participant

from . import schemas


def member_read(m: Member) -> schemas.MemberRead:
    return schemas.MemberRead(
        id=m.id,
        first_name=m.first_name,
        last_name=m.last_name,
        date_of_birth=m.date_of_birth,
        weight=m.weight,
        gender=m.gender,
        club_id=m.club_id,
        age=m.age,
        age_category=m.age_category,
        weight_updated_at=m.weight_updated_at,
        is_complete=m.is_complete,
    )


def participant_read(
    session: Session,
    p: Participant,
    *,
    member: Member | None = None,
    group_name: str | None = None,
) -> schemas.ParticipantRead:
    member = member or crud.get_by_id(session, Member, p.member_id)
    name = f"{member.first_name} {member.last_name}" if member else "?"
    return schemas.ParticipantRead(
        id=p.id,
        member_id=p.member_id,
        tournament_id=p.tournament_id,
        group_id=p.group_id,
        member_name=name,
        gender=member.gender if member else "",
        weight=member.weight if member else 0.0,
        age_category=member.age_category if member else "",
        club_id=member.club_id if member else None,
        group_name=group_name,
    )


def participant_name_map(
    session: Session, tournament_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    """Map participant_id -> 'First Last' for a tournament."""
    out: dict[uuid.UUID, str] = {}
    for p in crud.get_participants_by_tournament(session, tournament_id):
        member = crud.get_by_id(session, Member, p.member_id)
        out[p.id] = f"{member.first_name} {member.last_name}" if member else "?"
    return out


def match_read(m: Match, names: dict[uuid.UUID, str]) -> schemas.MatchRead:
    return schemas.MatchRead(
        id=m.id,
        group_id=m.group_id,
        participant_a_id=m.participant_a_id,
        participant_b_id=m.participant_b_id,
        name_a=names.get(m.participant_a_id, "?"),
        name_b=names.get(m.participant_b_id, "?"),
        winner_id=m.winner_id,
        score_a_ippon=m.score_a_ippon,
        score_a_wazari=m.score_a_wazari,
        score_a_yuko=m.score_a_yuko,
        score_b_ippon=m.score_b_ippon,
        score_b_wazari=m.score_b_wazari,
        score_b_yuko=m.score_b_yuko,
        completed=m.completed,
    )
