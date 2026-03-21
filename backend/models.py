from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    last_name: str
    first_name: str
    club: str
    sex: str
    age_category: str
    weight: float


class TournamentGroup(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    sex: Optional[str] = None
    age_category: Optional[str] = None


class GroupMembership(SQLModel, table=True):
    participant_id: int = Field(foreign_key="participant.id", primary_key=True)
    group_id: int = Field(foreign_key="tournamentgroup.id", primary_key=True)


class MatchResult(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="tournamentgroup.id")
    participant_a_id: int = Field(foreign_key="participant.id")
    participant_b_id: int = Field(foreign_key="participant.id")
    winner_id: int = Field(foreign_key="participant.id")
    notes: str = ""
