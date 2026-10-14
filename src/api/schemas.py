"""Pydantic request/response schemas for the API layer.

These are deliberately separate from the SQLModel table models so the wire
format stays stable and never leaks password hashes.
"""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class CoachLogin(BaseModel):
    email: str
    password: str


class AdminLogin(BaseModel):
    username: str
    password: str


class RefereeLogin(BaseModel):
    token: str
    # Optional: the open tournament the user picked — must match the token.
    tournament_id: uuid.UUID | None = None


class InscriptionLogin(BaseModel):
    token: str
    tournament_id: uuid.UUID | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    display_name: str
    club_id: str | None = None
    tournament_id: str | None = None


class AdminSetup(BaseModel):
    username: str
    password: str


class SetupStatus(BaseModel):
    needs_setup: bool


# ---------------------------------------------------------------------------
# Clubs / coaches / members
# ---------------------------------------------------------------------------


class ClubCreate(BaseModel):
    name: str
    location: str = ""


class ClubRead(BaseModel):
    id: uuid.UUID
    name: str
    location: str


class CoachCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone_number: str = ""
    password: str


class CoachRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone_number: str
    club_id: uuid.UUID


class MemberCreate(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: date | None = None
    weight: float | None = None


class MemberUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: date | None = None
    weight: float | None = None
    gender: str | None = None


class MemberRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    date_of_birth: date | None = None
    weight: float | None = None
    gender: str
    club_id: uuid.UUID
    age: int | None = None
    age_category: str
    weight_updated_at: date | None = None
    is_complete: bool = True


# ---------------------------------------------------------------------------
# Tournaments / participants / groups
# ---------------------------------------------------------------------------


class TournamentCreate(BaseModel):
    name: str
    date: date
    location: str = ""
    hosting_club_id: uuid.UUID


class TournamentRead(BaseModel):
    id: uuid.UUID
    name: str
    date: date
    location: str
    hosting_club_id: uuid.UUID
    status: str = "closed"
    reweigh_months: int = 3


class TournamentStatusUpdate(BaseModel):
    status: str  # "open" | "closed"


class TournamentSettingsUpdate(BaseModel):
    reweigh_months: int


class PublicTournament(BaseModel):
    """Minimal tournament info exposed without authentication."""

    id: uuid.UUID
    name: str
    date: date
    location: str


class ParticipantRead(BaseModel):
    id: uuid.UUID
    member_id: uuid.UUID
    tournament_id: uuid.UUID
    group_id: uuid.UUID | None
    member_name: str
    gender: str
    weight: float | None = None
    age_category: str
    club_id: uuid.UUID | None = None
    group_name: str | None = None


class RegisterParticipants(BaseModel):
    member_ids: list[uuid.UUID]


class RegistrationRow(BaseModel):
    """One member as seen from the inscription desk for a tournament."""

    member_id: uuid.UUID
    member_name: str
    first_name: str
    last_name: str
    club_name: str
    gender: str
    weight: float | None = None
    registered: bool
    weight_updated_at: date | None = None
    weight_stale: bool = False


class GroupConfig(BaseModel):
    max_group_size: int = 4
    max_additional_groups: int = 2


class SetGroupParticipants(BaseModel):
    participant_ids: list[uuid.UUID]


class GroupRead(BaseModel):
    id: uuid.UUID
    name: str
    tournament_id: uuid.UUID
    participants: list[ParticipantRead] = []


# ---------------------------------------------------------------------------
# Matches / standings
# ---------------------------------------------------------------------------


class MatchRead(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    participant_a_id: uuid.UUID
    participant_b_id: uuid.UUID
    name_a: str
    name_b: str
    winner_id: uuid.UUID | None
    score_a_ippon: int
    score_a_wazari: int
    score_a_yuko: int
    score_b_ippon: int
    score_b_wazari: int
    score_b_yuko: int
    completed: bool


class ScoreAction(BaseModel):
    side: str  # "a" | "b"
    point: str  # "ippon" | "wazari" | "yuko"


class StandingRow(BaseModel):
    participant_id: uuid.UUID
    name: str
    wins: int
    draws: int
    losses: int
    points: int


# ---------------------------------------------------------------------------
# Referee tokens
# ---------------------------------------------------------------------------


class TokenCreate(BaseModel):
    label: str
    role: str = "referee"  # "referee" | "inscription"
    token: str | None = None  # optional custom value; auto-generated when omitted


class TokenUpdate(BaseModel):
    token: str | None = None
    label: str | None = None


class RefereeTokenRead(BaseModel):
    id: uuid.UUID
    token: str
    label: str
    tournament_id: uuid.UUID
    role: str = "referee"


# ---------------------------------------------------------------------------
# Results (coach view)
# ---------------------------------------------------------------------------


class MemberResult(BaseModel):
    member_id: uuid.UUID
    member_name: str
    group_label: str
    wins: int
    draws: int
    losses: int
    rank: int | None = None
    group_size: int | None = None


class TournamentResult(BaseModel):
    tournament_id: uuid.UUID
    tournament_name: str
    date: date
    members: list[MemberResult]


class ClubResults(BaseModel):
    total_wins: int
    total_draws: int
    total_losses: int
    tournaments: list[TournamentResult]
