"""Shared fixtures for the judo-tournament test suite."""

import uuid
from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine

from backend.database.models import (
    Club,
    Coach,
    Group,
    Member,
    Participant,
    Tournament,
)


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def engine():
    """In-memory SQLite engine — tables created fresh for every test."""
    eng = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(eng)
    yield eng
    SQLModel.metadata.drop_all(eng)


@pytest.fixture()
def session(engine):
    """Database session bound to the in-memory engine."""
    with Session(engine) as s:
        yield s


# ---------------------------------------------------------------------------
# Factory helpers (return *unsaved* objects — call crud.create in the test)
# ---------------------------------------------------------------------------

def make_club(*, name: str = "Judo Club Test", location: str = "Paris") -> Club:
    return Club(name=name, location=location)


def make_coach(
    club_id: uuid.UUID,
    *,
    first_name: str = "Sensei",
    last_name: str = "Tanaka",
    phone_number: str = "0600000000",
    email: str = "sensei@club.fr",
) -> Coach:
    return Coach(
        first_name=first_name,
        last_name=last_name,
        club_id=club_id,
        phone_number=phone_number,
        email=email,
    )


def make_member(
    club_id: uuid.UUID,
    *,
    first_name: str = "Jean",
    last_name: str = "Dupont",
    date_of_birth: date = date(1998, 3, 15),
    weight: float = 73.0,
    gender: str = "M",
) -> Member:
    return Member(
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        weight=weight,
        gender=gender,
        club_id=club_id,
    )


def make_tournament(
    hosting_club_id: uuid.UUID,
    *,
    name: str = "Open de Paris",
    tournament_date: date = date(2026, 6, 15),
    location: str = "Paris",
) -> Tournament:
    return Tournament(
        name=name,
        date=tournament_date,
        location=location,
        hosting_club_id=hosting_club_id,
    )


def make_group(
    tournament_id: uuid.UUID,
    *,
    name: str = "Pool A",
) -> Group:
    return Group(name=name, tournament_id=tournament_id)


# ---------------------------------------------------------------------------
# Pre-populated "dummy database" fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def dummy_db(session):
    """Populate the in-memory DB with realistic sample data.

    Returns a dict with handles to the created objects so tests can
    reference them without extra queries.
    """
    # Clubs
    club_a = Club(name="Judo Club Lyon", location="Lyon")
    club_b = Club(name="Judo Club Marseille", location="Marseille")
    session.add_all([club_a, club_b])
    session.commit()
    session.refresh(club_a)
    session.refresh(club_b)

    # Coaches
    coach = Coach(
        first_name="Yuki", last_name="Tanaka",
        club_id=club_a.id, phone_number="0612345678", email="yuki@lyon.fr",
    )
    session.add(coach)

    # Members — spread across both clubs, mixed gender & weight
    members_data = [
        ("Jean", "Dupont", date(1998, 3, 15), 73.0, "M", club_a.id),
        ("Marie", "Bernard", date(2005, 7, 22), 60.0, "F", club_a.id),
        ("Luc", "Durand", date(2000, 1, 10), 81.0, "M", club_a.id),
        ("Sophie", "Petit", date(1999, 12, 1), 57.0, "F", club_b.id),
        ("Pierre", "Martin", date(2003, 5, 5), 66.0, "M", club_b.id),
        ("Claire", "Leroy", date(2001, 9, 20), 52.0, "F", club_b.id),
        ("Hugo", "Garcia", date(1997, 4, 8), 90.0, "M", club_a.id),
        ("Emma", "Michel", date(2004, 11, 30), 48.0, "F", club_b.id),
    ]
    members = []
    for fn, ln, dob, w, g, cid in members_data:
        m = Member(
            first_name=fn, last_name=ln, date_of_birth=dob,
            weight=w, gender=g, club_id=cid,
        )
        members.append(m)
    session.add_all(members)
    session.commit()
    for m in members:
        session.refresh(m)
    session.refresh(coach)

    # Tournament
    tournament = Tournament(
        name="Open de Lyon", date=date(2026, 6, 15),
        location="Lyon", hosting_club_id=club_a.id,
    )
    session.add(tournament)
    session.commit()
    session.refresh(tournament)

    # Group
    group = Group(name="Pool A", tournament_id=tournament.id)
    session.add(group)
    session.commit()
    session.refresh(group)

    # Participants — first 4 members registered, 2 assigned to the group
    participants = []
    for i, m in enumerate(members[:4]):
        p = Participant(
            member_id=m.id,
            tournament_id=tournament.id,
            group_id=group.id if i < 2 else None,
        )
        participants.append(p)
    session.add_all(participants)
    session.commit()
    for p in participants:
        session.refresh(p)

    return {
        "clubs": [club_a, club_b],
        "coach": coach,
        "members": members,
        "tournament": tournament,
        "group": group,
        "participants": participants,
    }
