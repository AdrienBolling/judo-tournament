"""Tests for backend.database.crud — generic + domain-specific queries."""

import uuid
from datetime import date

import pytest

from backend.database import crud
from backend.database.models import (
    Club,
    Coach,
    Group,
    Member,
    Participant,
    Tournament,
)

from .conftest import make_club, make_coach, make_member, make_tournament, make_group


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

class TestCreate:
    def test_create_returns_object_with_id(self, session):
        club = crud.create(session, make_club())
        assert club.id is not None
        assert club.name == "Judo Club Test"

    def test_create_persists(self, session):
        club = crud.create(session, make_club())
        fetched = crud.get_by_id(session, Club, club.id)
        assert fetched is not None
        assert fetched.name == club.name


class TestCreateAll:
    def test_batch_creation(self, session):
        clubs = crud.create_all(session, [make_club(name="A"), make_club(name="B")])
        assert len(clubs) == 2
        assert {c.name for c in clubs} == {"A", "B"}

    def test_all_persisted(self, session):
        crud.create_all(session, [make_club(name="X"), make_club(name="Y")])
        assert len(crud.get_all(session, Club)) == 2


class TestGetById:
    def test_existing(self, session):
        club = crud.create(session, make_club())
        assert crud.get_by_id(session, Club, club.id) is not None

    def test_missing(self, session):
        assert crud.get_by_id(session, Club, uuid.uuid4()) is None


class TestGetAll:
    def test_empty_table(self, session):
        assert crud.get_all(session, Club) == []

    def test_returns_all(self, session):
        crud.create_all(session, [make_club(name="A"), make_club(name="B"), make_club(name="C")])
        assert len(crud.get_all(session, Club)) == 3


class TestUpdate:
    def test_update_field(self, session):
        club = crud.create(session, make_club(name="Old"))
        crud.update(session, club, name="New")
        fetched = crud.get_by_id(session, Club, club.id)
        assert fetched.name == "New"

    def test_update_preserves_other_fields(self, session):
        club = crud.create(session, make_club(name="Club", location="Lyon"))
        crud.update(session, club, name="Renamed")
        assert club.location == "Lyon"


class TestDelete:
    def test_delete_removes(self, session):
        club = crud.create(session, make_club())
        crud.delete(session, club)
        assert crud.get_by_id(session, Club, club.id) is None

    def test_delete_only_target(self, session):
        c1 = crud.create(session, make_club(name="Keep"))
        c2 = crud.create(session, make_club(name="Remove"))
        crud.delete(session, c2)
        assert crud.get_by_id(session, Club, c1.id) is not None
        assert crud.get_by_id(session, Club, c2.id) is None


# ---------------------------------------------------------------------------
# Club queries
# ---------------------------------------------------------------------------

class TestGetClubByName:
    def test_found(self, session):
        crud.create(session, make_club(name="ABC"))
        assert crud.get_club_by_name(session, "ABC") is not None

    def test_not_found(self, session):
        assert crud.get_club_by_name(session, "Nonexistent") is None


# ---------------------------------------------------------------------------
# Member queries
# ---------------------------------------------------------------------------

class TestGetMembersByClub:
    def test_filters_by_club(self, session):
        c1 = crud.create(session, make_club(name="C1"))
        c2 = crud.create(session, make_club(name="C2"))
        crud.create(session, make_member(c1.id, first_name="A"))
        crud.create(session, make_member(c1.id, first_name="B"))
        crud.create(session, make_member(c2.id, first_name="C"))

        result = crud.get_members_by_club(session, c1.id)
        assert len(result) == 2
        assert all(m.club_id == c1.id for m in result)

    def test_empty_club(self, session):
        club = crud.create(session, make_club())
        assert crud.get_members_by_club(session, club.id) == []


# ---------------------------------------------------------------------------
# Coach queries
# ---------------------------------------------------------------------------

class TestGetCoachesByClub:
    def test_filters_by_club(self, session):
        club = crud.create(session, make_club())
        crud.create(session, make_coach(club.id, first_name="A"))
        crud.create(session, make_coach(club.id, first_name="B"))

        result = crud.get_coaches_by_club(session, club.id)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Tournament / Participant / Group queries (use dummy_db)
# ---------------------------------------------------------------------------

class TestTournamentQueries:
    def test_get_tournaments(self, session, dummy_db):
        tournaments = crud.get_tournaments(session)
        assert len(tournaments) == 1
        assert tournaments[0].name == "Open de Lyon"


class TestParticipantQueries:
    def test_get_participants_by_tournament(self, session, dummy_db):
        tid = dummy_db["tournament"].id
        participants = crud.get_participants_by_tournament(session, tid)
        assert len(participants) == 4

    def test_get_unassigned_participants(self, session, dummy_db):
        tid = dummy_db["tournament"].id
        unassigned = crud.get_unassigned_participants(session, tid)
        # First 2 are assigned, last 2 are not
        assert len(unassigned) == 2
        assert all(p.group_id is None for p in unassigned)


class TestGroupQueries:
    def test_get_groups_by_tournament(self, session, dummy_db):
        tid = dummy_db["tournament"].id
        groups = crud.get_groups_by_tournament(session, tid)
        assert len(groups) == 1
        assert groups[0].name == "Pool A"

    def test_empty_tournament(self, session, dummy_db):
        club = dummy_db["clubs"][0]
        t = crud.create(session, Tournament(
            name="Empty", date=date(2026, 1, 1),
            location="Nowhere", hosting_club_id=club.id,
        ))
        assert crud.get_groups_by_tournament(session, t.id) == []
