"""Tests for backend.utils — CSV bulk import."""

import textwrap
from datetime import date
from pathlib import Path

import pytest

from backend.database import crud
from backend.database.models import Club
from backend.utils import import_members_from_csv

from .conftest import make_club


@pytest.fixture()
def club(session) -> Club:
    """A persisted club to import members into."""
    return crud.create(session, make_club())


@pytest.fixture()
def csv_file(tmp_path) -> Path:
    """Write a valid CSV and return its path."""
    content = textwrap.dedent("""\
        first_name,last_name,date_of_birth,weight,gender
        Jean,Dupont,15/03/1998,73.0,M
        Marie,Bernard,2005-07-22,60.0,F
        Luc,Durand,01/09/2015,35.0,M
    """)
    path = tmp_path / "members.csv"
    path.write_text(content)
    return path


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestImportCSV:
    def test_returns_all_members(self, session, club, csv_file):
        members = import_members_from_csv(session, csv_file, club.id)
        assert len(members) == 3

    def test_members_persisted(self, session, club, csv_file):
        import_members_from_csv(session, csv_file, club.id)
        assert len(crud.get_members_by_club(session, club.id)) == 3

    def test_fields_parsed_correctly(self, session, club, csv_file):
        members = import_members_from_csv(session, csv_file, club.id)
        jean = next(m for m in members if m.first_name == "Jean")
        assert jean.last_name == "Dupont"
        assert jean.date_of_birth == date(1998, 3, 15)
        assert jean.weight == 73.0
        assert jean.gender == "M"
        assert jean.club_id == club.id

    def test_iso_dates_parsed(self, session, club, csv_file):
        members = import_members_from_csv(session, csv_file, club.id)
        marie = next(m for m in members if m.first_name == "Marie")
        assert marie.date_of_birth == date(2005, 7, 22)

    def test_french_dates_parsed(self, session, club, csv_file):
        members = import_members_from_csv(session, csv_file, club.id)
        luc = next(m for m in members if m.first_name == "Luc")
        assert luc.date_of_birth == date(2015, 9, 1)

    def test_whitespace_stripped(self, session, club, tmp_path):
        content = textwrap.dedent("""\
            first_name , last_name , date_of_birth , weight , gender
             Alice , Martin ,01/01/2000, 55.0 , F
        """)
        path = tmp_path / "spaces.csv"
        path.write_text(content)
        members = import_members_from_csv(session, path, club.id)
        assert members[0].first_name == "Alice"
        assert members[0].last_name == "Martin"
        assert members[0].gender == "F"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestImportCSVErrors:
    def test_missing_column_raises(self, session, club, tmp_path):
        content = textwrap.dedent("""\
            first_name,last_name,weight,gender
            Jean,Dupont,73.0,M
        """)
        path = tmp_path / "bad.csv"
        path.write_text(content)
        with pytest.raises(ValueError, match="Missing CSV columns"):
            import_members_from_csv(session, path, club.id)
