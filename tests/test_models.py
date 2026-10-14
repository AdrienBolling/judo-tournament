"""Tests for backend.database.models — age helpers, properties, DataFrame conversion."""

from datetime import date

import pytest

from backend.database.models import (
    AGE_CATEGORIES,
    Member,
    _compute_age,
    age_to_category,
    members_to_df,
)

from .conftest import make_club, make_member


# ---------------------------------------------------------------------------
# _compute_age
# ---------------------------------------------------------------------------

class TestComputeAge:
    def test_exact_birthday(self):
        assert _compute_age(date(2000, 6, 15), ref=date(2026, 6, 15)) == 26

    def test_day_before_birthday(self):
        assert _compute_age(date(2000, 6, 15), ref=date(2026, 6, 14)) == 25

    def test_day_after_birthday(self):
        assert _compute_age(date(2000, 6, 15), ref=date(2026, 6, 16)) == 26

    def test_newborn(self):
        assert _compute_age(date(2026, 1, 1), ref=date(2026, 1, 1)) == 0

    def test_leap_year_birthday(self):
        # Born Feb 29 — on Feb 28 the next year they're still 0
        assert _compute_age(date(2000, 2, 29), ref=date(2001, 2, 28)) == 0
        assert _compute_age(date(2000, 2, 29), ref=date(2001, 3, 1)) == 1


# ---------------------------------------------------------------------------
# age_to_category
# ---------------------------------------------------------------------------

class TestAgeToCategory:
    @pytest.mark.parametrize(
        "age, expected",
        [
            (3, "Mini-poussin"),
            (5, "Mini-poussin"),
            (6, "Poussin"),
            (7, "Poussin"),
            (8, "Benjamin"),
            (9, "Benjamin"),
            (10, "Minime"),
            (11, "Minime"),
            (12, "Cadet"),
            (14, "Cadet"),
            (15, "Junior"),
            (17, "Junior"),
            (18, "Senior"),
            (34, "Senior"),
            (35, "Vétéran"),
            (70, "Vétéran"),
        ],
    )
    def test_category_boundaries(self, age, expected):
        assert age_to_category(age) == expected

    def test_covers_all_ages_0_to_100(self):
        for age in range(101):
            assert age_to_category(age) != "Unknown"


# ---------------------------------------------------------------------------
# Member properties
# ---------------------------------------------------------------------------

class TestMemberProperties:
    def test_age_category_senior(self):
        club = make_club()
        m = make_member(club.id, date_of_birth=date(1998, 3, 15))
        assert m.age_category == "Senior"

    def test_age_category_minime(self):
        club = make_club()
        m = make_member(club.id, date_of_birth=date(2016, 1, 1))
        assert m.age_category == "Minime"

    def test_age_returns_int(self):
        club = make_club()
        m = make_member(club.id)
        assert isinstance(m.age, int)
        assert m.age > 0


# ---------------------------------------------------------------------------
# members_to_df
# ---------------------------------------------------------------------------

class TestMembersToDf:
    def test_columns_present(self):
        club = make_club()
        members = [
            make_member(club.id, first_name="A"),
            make_member(club.id, first_name="B"),
        ]
        df = members_to_df(members)
        assert "age_category" in df.columns
        assert "weight" in df.columns
        assert "club_id" in df.columns
        assert "date_of_birth" in df.columns

    def test_row_count(self):
        club = make_club()
        members = [make_member(club.id) for _ in range(5)]
        df = members_to_df(members)
        assert len(df) == 5

    def test_weight_is_numeric(self):
        club = make_club()
        df = members_to_df([make_member(club.id, weight=73.5)])
        assert df["weight"].dtype == float
