import uuid
from datetime import date

import pandas as pd
from sqlmodel import Field, Relationship, SQLModel

# ---------------------------------------------------------------------------
# Age-category helpers
# ---------------------------------------------------------------------------

AGE_CATEGORIES: list[tuple[int, int, str]] = [
    (0, 5, "Mini-poussin"),
    (6, 7, "Poussin"),
    (8, 9, "Benjamin"),
    (10, 11, "Minime"),
    (12, 14, "Cadet"),
    (15, 17, "Junior"),
    (18, 34, "Senior"),
    (35, 999, "Vétéran"),
]


def _compute_age(birth: date, ref: date | None = None) -> int:
    """Return age in whole years at *ref* date (defaults to today)."""
    ref = ref or date.today()
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))


def age_to_category(age: int) -> str:
    """Map an age to its judo category using ``AGE_CATEGORIES``."""
    for min_age, max_age, category in AGE_CATEGORIES:
        if min_age <= age <= max_age:
            return category
    return "Unknown"


# ---------------------------------------------------------------------------
# Models — ordered so that forward references are only needed for lists
# ---------------------------------------------------------------------------

class Club(SQLModel, table=True):
    """Model for a Judo Club."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    location: str

    coaches: list["Coach"] = Relationship(back_populates="club")
    members: list["Member"] = Relationship(back_populates="club")
    hosted_tournaments: list["Tournament"] = Relationship(back_populates="hosting_club")


class Coach(SQLModel, table=True):
    """Model for a Judo Coach."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    last_name: str
    first_name: str
    club_id: uuid.UUID = Field(foreign_key="club.id")
    phone_number: str
    email: str
    password_hash: str | None = Field(default=None)

    club: Club | None = Relationship(back_populates="coaches")


class Member(SQLModel, table=True):
    """Model for a member of a Judo Club."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    last_name: str
    first_name: str
    # date_of_birth and weight are optional: a member can be created with just
    # name + gender and completed later via the members page.
    date_of_birth: date | None = Field(default=None)
    weight: float | None = Field(default=None)
    gender: str
    club_id: uuid.UUID = Field(foreign_key="club.id")
    # Date the weight was last recorded/updated (for reweigh reminders). None
    # until a weight has actually been recorded.
    weight_updated_at: date | None = Field(default=None)

    club: Club | None = Relationship(back_populates="members")
    participations: list["Participant"] = Relationship(back_populates="member")

    @property
    def age(self) -> int | None:
        """Age in whole years as of today, or None if no birth date."""
        if self.date_of_birth is None:
            return None
        return _compute_age(self.date_of_birth)

    @property
    def age_category(self) -> str:
        """Judo age category derived from ``date_of_birth`` ('' if unknown)."""
        age = self.age
        return age_to_category(age) if age is not None else ""

    @property
    def is_complete(self) -> bool:
        """True when weight and birth date are both filled in."""
        return self.weight is not None and self.date_of_birth is not None


class AdminUser(SQLModel, table=True):
    """Administrator account."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str


class Tournament(SQLModel, table=True):
    """Model for a Judo Tournament."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    date: date
    location: str
    hosting_club_id: uuid.UUID = Field(foreign_key="club.id")
    # Lifecycle: "closed" (draft) → "open" (visible to referee/inscription flows).
    status: str = Field(default="closed")
    # Reweigh reminder threshold (months) — warn at registration if a member's
    # weight hasn't been updated within this many months.
    reweigh_months: int = Field(default=3)

    hosting_club: Club | None = Relationship(back_populates="hosted_tournaments")
    participants: list["Participant"] = Relationship(back_populates="tournament")
    groups: list["Group"] = Relationship(back_populates="tournament")
    referee_tokens: list["RefereeToken"] = Relationship(back_populates="tournament")


class RefereeToken(SQLModel, table=True):
    """Token granting a referee access to a tournament's scoring panels."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token: str = Field(unique=True, index=True)
    label: str
    tournament_id: uuid.UUID = Field(foreign_key="tournament.id")
    # Access kind granted by this token: "referee" or "inscription".
    role: str = Field(default="referee")

    tournament: Tournament | None = Relationship(back_populates="referee_tokens")


class Group(SQLModel, table=True):
    """Model for a round-robin pool in a Judo Tournament."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    tournament_id: uuid.UUID = Field(foreign_key="tournament.id")

    tournament: Tournament | None = Relationship(back_populates="groups")
    participants: list["Participant"] = Relationship(back_populates="group")
    matches: list["Match"] = Relationship(back_populates="group")


class Match(SQLModel, table=True):
    """A single bout between two participants in a group."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: uuid.UUID = Field(foreign_key="group.id")

    # Participant references (no ORM Relationship — multiple FKs to same table)
    participant_a_id: uuid.UUID = Field(foreign_key="participant.id")
    participant_b_id: uuid.UUID = Field(foreign_key="participant.id")
    winner_id: uuid.UUID | None = Field(default=None)

    # Scores
    score_a_ippon: int = Field(default=0)
    score_a_wazari: int = Field(default=0)
    score_a_yuko: int = Field(default=0)
    score_b_ippon: int = Field(default=0)
    score_b_wazari: int = Field(default=0)
    score_b_yuko: int = Field(default=0)
    completed: bool = Field(default=False)

    group: Group | None = Relationship(back_populates="matches")


class Participant(SQLModel, table=True):
    """Model for a participant in a Judo Tournament."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    member_id: uuid.UUID = Field(foreign_key="member.id")
    tournament_id: uuid.UUID = Field(foreign_key="tournament.id")
    group_id: uuid.UUID | None = Field(default=None, foreign_key="group.id")

    member: Member | None = Relationship(back_populates="participations")
    tournament: Tournament | None = Relationship(back_populates="participants")
    group: Group | None = Relationship(back_populates="participants")


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def members_to_df(members_list: list[Member]) -> pd.DataFrame:
    """Convert a list of Member objects to a pandas DataFrame.

    Includes the computed ``age_category`` column.
    """
    df = pd.DataFrame.from_records([m.model_dump() for m in members_list])
    df["age_category"] = [m.age_category for m in members_list]
    return df
