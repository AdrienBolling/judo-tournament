"""Authentication + first-run admin setup."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.auth import hash_password, verify_password
from backend.database import crud
from backend.database.models import AdminUser

from .. import schemas
from ..deps import current_principal, db_session
from ..security import Principal, create_token

router = APIRouter(tags=["auth"])


@router.get("/setup/status", response_model=schemas.SetupStatus)
def setup_status(session: Session = Depends(db_session)) -> schemas.SetupStatus:
    return schemas.SetupStatus(needs_setup=len(crud.get_all(session, AdminUser)) == 0)


@router.post("/setup/admin", response_model=schemas.TokenResponse)
def setup_admin(
    body: schemas.AdminSetup, session: Session = Depends(db_session)
) -> schemas.TokenResponse:
    if crud.get_all(session, AdminUser):
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin already exists")
    if not body.username or not body.password:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username and password required")
    admin = crud.create(
        session, AdminUser(username=body.username, password_hash=hash_password(body.password))
    )
    principal = Principal(
        role="admin", user_id=str(admin.id), display_name=f"Admin ({admin.username})"
    )
    return _token_response(principal)


@router.post("/auth/login/admin", response_model=schemas.TokenResponse)
def login_admin(
    body: schemas.AdminLogin, session: Session = Depends(db_session)
) -> schemas.TokenResponse:
    admin = crud.get_admin_by_username(session, body.username.strip())
    if not admin or not verify_password(body.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    principal = Principal(
        role="admin", user_id=str(admin.id), display_name=f"Admin ({admin.username})"
    )
    return _token_response(principal)


@router.post("/auth/login/coach", response_model=schemas.TokenResponse)
def login_coach(
    body: schemas.CoachLogin, session: Session = Depends(db_session)
) -> schemas.TokenResponse:
    coach = crud.get_coach_by_email(session, body.email.strip())
    if not coach or not coach.password_hash or not verify_password(body.password, coach.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    principal = Principal(
        role="coach",
        user_id=str(coach.id),
        club_id=str(coach.club_id),
        display_name=f"{coach.first_name} {coach.last_name}",
    )
    return _token_response(principal)


@router.post("/auth/login/referee", response_model=schemas.TokenResponse)
def login_referee(
    body: schemas.RefereeLogin, session: Session = Depends(db_session)
) -> schemas.TokenResponse:
    ref = _resolve_token(session, body.token, body.tournament_id, "referee")
    principal = Principal(
        role="referee",
        tournament_id=str(ref.tournament_id),
        display_name=f"Referee ({ref.label})",
    )
    return _token_response(principal)


@router.post("/auth/login/inscription", response_model=schemas.TokenResponse)
def login_inscription(
    body: schemas.InscriptionLogin, session: Session = Depends(db_session)
) -> schemas.TokenResponse:
    ref = _resolve_token(session, body.token, body.tournament_id, "inscription")
    principal = Principal(
        role="inscription",
        tournament_id=str(ref.tournament_id),
        display_name=f"Inscriptions ({ref.label})",
    )
    return _token_response(principal)


def _resolve_token(session, token: str, tournament_id, expected_role: str):
    """Look up an access token, enforcing its role and (optional) tournament."""
    ref = crud.get_referee_token_by_value(session, token.strip())
    if not ref or ref.role != expected_role:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if tournament_id is not None and ref.tournament_id != tournament_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Token does not match the selected tournament"
        )
    return ref


@router.get("/auth/me", response_model=schemas.TokenResponse)
def me(principal: Principal = Depends(current_principal)) -> schemas.TokenResponse:
    # Re-issue a token alongside the principal so the client can refresh state.
    return _token_response(principal)


def _token_response(principal: Principal) -> schemas.TokenResponse:
    return schemas.TokenResponse(
        access_token=create_token(principal),
        role=principal.role,
        display_name=principal.display_name,
        club_id=principal.club_id,
        tournament_id=principal.tournament_id,
    )
