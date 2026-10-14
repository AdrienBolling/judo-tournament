"""Clubs, coaches and members.

Authorisation model:
- Admins can read/write everything.
- Coaches can read/write members of their own club only.
"""

from __future__ import annotations

import tempfile
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlmodel import Session

from backend.auth import hash_password
from backend.database import crud
from backend.database.models import Club, Coach, Member
from backend.utils import import_members_from_csv

from .. import schemas
from ..deps import current_principal, db_session, require_roles
from ..security import Principal
from ..serializers import member_read

router = APIRouter(tags=["clubs"])


def _assert_club_access(principal: Principal, club_id: uuid.UUID) -> None:
    """Coaches may only touch their own club; admins anything."""
    if principal.role == "admin":
        return
    if principal.role == "coach" and principal.club_id == str(club_id):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for this club")


# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------


@router.get("/clubs", response_model=list[schemas.ClubRead])
def list_clubs(
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[Club]:
    return crud.get_all(session, Club)


@router.post("/clubs", response_model=schemas.ClubRead, status_code=status.HTTP_201_CREATED)
def create_club(
    body: schemas.ClubCreate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> Club:
    if not body.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Club name is required")
    return crud.create(session, Club(name=body.name, location=body.location))


# ---------------------------------------------------------------------------
# Coaches
# ---------------------------------------------------------------------------


@router.get("/clubs/{club_id}/coaches", response_model=list[schemas.CoachRead])
def list_coaches(
    club_id: uuid.UUID,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> list[Coach]:
    return crud.get_coaches_by_club(session, club_id)


@router.post(
    "/clubs/{club_id}/coaches",
    response_model=schemas.CoachRead,
    status_code=status.HTTP_201_CREATED,
)
def create_coach(
    club_id: uuid.UUID,
    body: schemas.CoachCreate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> Coach:
    if crud.get_coach_by_email(session, body.email.strip()):
        raise HTTPException(status.HTTP_409_CONFLICT, "A coach with this email already exists")
    return crud.create(
        session,
        Coach(
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            email=body.email.strip(),
            phone_number=body.phone_number.strip(),
            club_id=club_id,
            password_hash=hash_password(body.password),
        ),
    )


@router.delete("/coaches/{coach_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coach(
    coach_id: uuid.UUID,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> None:
    coach = crud.get_by_id(session, Coach, coach_id)
    if not coach:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coach not found")
    crud.delete(session, coach)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/clubs/{club_id}/members", response_model=list[schemas.MemberRead])
def list_members(
    club_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[schemas.MemberRead]:
    _assert_club_access(principal, club_id)
    return [member_read(m) for m in crud.get_members_by_club(session, club_id)]


@router.post(
    "/clubs/{club_id}/members",
    response_model=schemas.MemberRead,
    status_code=status.HTTP_201_CREATED,
)
def create_member(
    club_id: uuid.UUID,
    body: schemas.MemberCreate,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> schemas.MemberRead:
    _assert_club_access(principal, club_id)
    member = crud.create(
        session,
        Member(
            first_name=body.first_name.strip(),
            last_name=body.last_name.strip(),
            date_of_birth=body.date_of_birth,
            weight=body.weight,
            gender=body.gender,
            club_id=club_id,
            # Stamp the weigh-in date only if a weight was actually provided.
            weight_updated_at=date.today() if body.weight is not None else None,
        ),
    )
    return member_read(member)


@router.patch("/members/{member_id}", response_model=schemas.MemberRead)
def update_member(
    member_id: uuid.UUID,
    body: schemas.MemberUpdate,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> schemas.MemberRead:
    """Edit a member. Updating the weight stamps ``weight_updated_at`` (a weigh-in)."""
    member = crud.get_by_id(session, Member, member_id)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member not found")
    # Admins and inscription staff (tournament desk) may edit any member;
    # coaches only their own club's members.
    if principal.role not in ("admin", "inscription"):
        _assert_club_access(principal, member.club_id)

    changes: dict = {}
    if body.first_name is not None:
        changes["first_name"] = body.first_name.strip()
    if body.last_name is not None:
        changes["last_name"] = body.last_name.strip()
    if body.date_of_birth is not None:
        changes["date_of_birth"] = body.date_of_birth
    if body.gender is not None:
        changes["gender"] = body.gender
    if body.weight is not None and body.weight != member.weight:
        # The weight changed → record the weigh-in date.
        changes["weight"] = body.weight
        changes["weight_updated_at"] = date.today()

    if changes:
        member = crud.update(session, member, **changes)
    return member_read(member)


@router.post("/clubs/{club_id}/members/import", response_model=list[schemas.MemberRead])
def import_members(
    club_id: uuid.UUID,
    file: UploadFile,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[schemas.MemberRead]:
    _assert_club_access(principal, club_id)
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp_file:
        tmp_file.write(file.file.read())
        tmp_path = Path(tmp_file.name)
    try:
        members = import_members_from_csv(session, tmp_path, club_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    finally:
        tmp_path.unlink(missing_ok=True)
    return [member_read(m) for m in members]
