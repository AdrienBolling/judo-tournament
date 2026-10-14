"""CRUD operations for judo tournament models."""

import uuid
from typing import TypeVar

from sqlmodel import Session, SQLModel, select

from sqlalchemy import or_

from .models import AdminUser, Club, Coach, Group, Match, Member, Participant, RefereeToken, Tournament

T = TypeVar("T", bound=SQLModel)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def create(session: Session, obj: T) -> T:
    """Add an object to the database, commit, and return it refreshed."""
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def create_all(session: Session, objects: list[T]) -> list[T]:
    """Add multiple objects in one transaction."""
    session.add_all(objects)
    session.commit()
    for obj in objects:
        session.refresh(obj)
    return objects


def get_by_id(session: Session, model: type[T], id: uuid.UUID) -> T | None:
    """Get an object by its primary key."""
    return session.get(model, id)


def get_all(session: Session, model: type[T]) -> list[T]:
    """Get all rows of a given model."""
    return list(session.exec(select(model)).all())


def update(session: Session, obj: T, **kwargs) -> T:
    """Update fields on an existing object."""
    for key, value in kwargs.items():
        setattr(obj, key, value)
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


def delete(session: Session, obj: T) -> None:
    """Delete an object from the database."""
    session.delete(obj)
    session.commit()


# ---------------------------------------------------------------------------
# Club
# ---------------------------------------------------------------------------

def get_club_by_name(session: Session, name: str) -> Club | None:
    return session.exec(select(Club).where(Club.name == name)).first()


# ---------------------------------------------------------------------------
# Member
# ---------------------------------------------------------------------------

def get_members_by_club(session: Session, club_id: uuid.UUID) -> list[Member]:
    return list(session.exec(select(Member).where(Member.club_id == club_id)).all())


# ---------------------------------------------------------------------------
# Coach
# ---------------------------------------------------------------------------

def get_coaches_by_club(session: Session, club_id: uuid.UUID) -> list[Coach]:
    return list(session.exec(select(Coach).where(Coach.club_id == club_id)).all())


# ---------------------------------------------------------------------------
# Tournament
# ---------------------------------------------------------------------------

def get_tournaments(session: Session) -> list[Tournament]:
    return list(session.exec(select(Tournament)).all())


def get_open_tournaments(session: Session) -> list[Tournament]:
    """Tournaments currently open (visible to referee / inscription flows)."""
    return list(session.exec(select(Tournament).where(Tournament.status == "open")).all())


# ---------------------------------------------------------------------------
# Participant
# ---------------------------------------------------------------------------

def get_participants_by_tournament(
    session: Session, tournament_id: uuid.UUID
) -> list[Participant]:
    return list(
        session.exec(
            select(Participant).where(Participant.tournament_id == tournament_id)
        ).all()
    )


def get_participant_by_member(
    session: Session, tournament_id: uuid.UUID, member_id: uuid.UUID
) -> Participant | None:
    """Return the participant row for a member in a tournament, if any."""
    return session.exec(
        select(Participant).where(
            Participant.tournament_id == tournament_id,
            Participant.member_id == member_id,
        )
    ).first()


def get_unassigned_participants(
    session: Session, tournament_id: uuid.UUID
) -> list[Participant]:
    """Get participants not yet assigned to a group."""
    return list(
        session.exec(
            select(Participant).where(
                Participant.tournament_id == tournament_id,
                Participant.group_id == None,  # noqa: E711 — SQLAlchemy requires ==
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------

def get_groups_by_tournament(
    session: Session, tournament_id: uuid.UUID
) -> list[Group]:
    return list(
        session.exec(
            select(Group).where(Group.tournament_id == tournament_id)
        ).all()
    )


# ---------------------------------------------------------------------------
# AdminUser
# ---------------------------------------------------------------------------

def get_admin_by_username(session: Session, username: str) -> AdminUser | None:
    return session.exec(select(AdminUser).where(AdminUser.username == username)).first()


# ---------------------------------------------------------------------------
# Coach (extras)
# ---------------------------------------------------------------------------

def get_coach_by_email(session: Session, email: str) -> Coach | None:
    return session.exec(select(Coach).where(Coach.email == email)).first()


# ---------------------------------------------------------------------------
# RefereeToken
# ---------------------------------------------------------------------------

def get_referee_tokens_by_tournament(
    session: Session, tournament_id: uuid.UUID
) -> list[RefereeToken]:
    return list(
        session.exec(
            select(RefereeToken).where(RefereeToken.tournament_id == tournament_id)
        ).all()
    )


def get_referee_token_by_value(session: Session, token: str) -> RefereeToken | None:
    return session.exec(
        select(RefereeToken).where(RefereeToken.token == token)
    ).first()


# ---------------------------------------------------------------------------
# Match
# ---------------------------------------------------------------------------

def get_matches_by_group(session: Session, group_id: uuid.UUID) -> list[Match]:
    return list(
        session.exec(select(Match).where(Match.group_id == group_id)).all()
    )


def get_matches_for_participant(
    session: Session, participant_id: uuid.UUID
) -> list[Match]:
    return list(
        session.exec(
            select(Match).where(
                or_(
                    Match.participant_a_id == participant_id,
                    Match.participant_b_id == participant_id,
                )
            )
        ).all()
    )


# ---------------------------------------------------------------------------
# Cross-entity helpers
# ---------------------------------------------------------------------------

def get_club_tournaments(session: Session, club_id: uuid.UUID) -> list[Tournament]:
    """Tournaments where at least one member of *club_id* participates."""
    members = get_members_by_club(session, club_id)
    if not members:
        return []
    member_ids = [m.id for m in members]
    participants = list(
        session.exec(
            select(Participant).where(Participant.member_id.in_(member_ids))
        ).all()
    )
    tournament_ids = list({p.tournament_id for p in participants})
    if not tournament_ids:
        return []
    return list(
        session.exec(
            select(Tournament).where(Tournament.id.in_(tournament_ids))
        ).all()
    )
