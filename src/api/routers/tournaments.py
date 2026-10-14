"""Tournaments, participant registration and group generation."""

from __future__ import annotations

import calendar
import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session

from backend.database import crud
from backend.database.models import Club, Group, Member, Tournament
from backend.solver.ga_solver import GAConfig
from backend.tournament import (
    register_members_for_tournament,
    set_group_participants,
    setup_tournament_groups,
    unregister_member_from_tournament,
)

from .. import schemas
from ..deps import current_principal, db_session, require_roles
from ..pdf import LABELS, PdfRow, build_participants_pdf
from ..security import Principal
from ..serializers import participant_read

router = APIRouter(tags=["tournaments"])

_DEFAULT_WEIGHTS = {"gender": 1.0, "weight": 3.0, "club": 1.0, "group_size": 0.5, "nb_groups": 0.5}


@router.get("/tournaments", response_model=list[schemas.TournamentRead])
def list_tournaments(
    session: Session = Depends(db_session),
    _: Principal = Depends(current_principal),
) -> list[Tournament]:
    return crud.get_tournaments(session)


@router.get("/public/open-tournaments", response_model=list[schemas.PublicTournament])
def public_open_tournaments(
    session: Session = Depends(db_session),
) -> list[Tournament]:
    """Open tournaments, exposed without auth for the referee/inscription logins."""
    return crud.get_open_tournaments(session)


@router.post(
    "/tournaments", response_model=schemas.TournamentRead, status_code=status.HTTP_201_CREATED
)
def create_tournament(
    body: schemas.TournamentCreate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> Tournament:
    if not body.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tournament name is required")
    return crud.create(
        session,
        Tournament(
            name=body.name,
            date=body.date,
            location=body.location,
            hosting_club_id=body.hosting_club_id,
        ),
    )


def _require_tournament(session: Session, tournament_id: uuid.UUID) -> Tournament:
    tournament = crud.get_by_id(session, Tournament, tournament_id)
    if not tournament:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tournament not found")
    return tournament


def _subtract_months(d: date, months: int) -> date:
    """Return the date *months* months before *d* (day clamped to month length)."""
    total = (d.year * 12 + d.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _assert_inscription_access(principal: Principal, tournament_id: uuid.UUID) -> None:
    """Allow admins anywhere; inscription staff only on their own tournament."""
    if principal.role == "admin":
        return
    if principal.role == "inscription" and principal.tournament_id == str(tournament_id):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for this tournament")


@router.patch("/tournaments/{tournament_id}/status", response_model=schemas.TournamentRead)
def set_tournament_status(
    tournament_id: uuid.UUID,
    body: schemas.TournamentStatusUpdate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> Tournament:
    if body.status not in ("open", "closed"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Status must be 'open' or 'closed'")
    tournament = _require_tournament(session, tournament_id)
    return crud.update(session, tournament, status=body.status)


@router.patch("/tournaments/{tournament_id}/settings", response_model=schemas.TournamentRead)
def set_tournament_settings(
    tournament_id: uuid.UUID,
    body: schemas.TournamentSettingsUpdate,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> Tournament:
    if body.reweigh_months < 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "reweigh_months must be at least 1")
    tournament = _require_tournament(session, tournament_id)
    return crud.update(session, tournament, reweigh_months=body.reweigh_months)


@router.get("/tournaments/{tournament_id}", response_model=schemas.TournamentRead)
def get_tournament(
    tournament_id: uuid.UUID,
    session: Session = Depends(db_session),
    _: Principal = Depends(current_principal),
) -> Tournament:
    return _require_tournament(session, tournament_id)


@router.get("/tournaments/{tournament_id}/participants.pdf")
def participants_pdf(
    tournament_id: uuid.UUID,
    gender: str | None = Query(default=None),
    club_id: uuid.UUID | None = Query(default=None),
    group_id: str | None = Query(default=None),
    lang: str = Query(default="fr"),
    session: Session = Depends(db_session),
    _: Principal = Depends(current_principal),
) -> Response:
    """Printable / downloadable participant sign-in sheet (filterable)."""
    tournament = _require_tournament(session, tournament_id)
    lang = lang if lang in LABELS else "fr"
    labels = LABELS[lang]

    clubs = {c.id: c.name for c in crud.get_all(session, Club)}
    groups = {g.id: g.name for g in crud.get_groups_by_tournament(session, tournament_id)}

    # Resolve the group filter: a UUID, the literal "unassigned", or nothing.
    group_uuid: uuid.UUID | None = None
    if group_id and group_id != "unassigned":
        try:
            group_uuid = uuid.UUID(group_id)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid group_id") from exc

    selected: list[tuple[Member, uuid.UUID | None]] = []
    for p in crud.get_participants_by_tournament(session, tournament_id):
        member = crud.get_by_id(session, Member, p.member_id)
        if member is None:
            continue
        if gender and member.gender != gender:
            continue
        if club_id and member.club_id != club_id:
            continue
        if group_id == "unassigned" and p.group_id is not None:
            continue
        if group_uuid is not None and p.group_id != group_uuid:
            continue
        selected.append((member, p.group_id))

    selected.sort(key=lambda mp: (mp[0].last_name.lower(), mp[0].first_name.lower()))
    rows = [
        PdfRow(
            name=f"{m.first_name} {m.last_name}",
            club=clubs.get(m.club_id, "—"),
            gender=m.gender,
            weight=m.weight,
        )
        for m, _gid in selected
    ]

    # Filter summary line for the header.
    summary_parts = [
        clubs.get(club_id, "—") if club_id else labels["allClubs"],
        gender if gender else labels["allGenders"],
        (
            labels["unassigned"]
            if group_id == "unassigned"
            else groups.get(group_uuid, "—") if group_uuid else labels["allPools"]
        ),
    ]
    subtitle = " · ".join(filter(None, [str(tournament.date), tournament.location]))

    pdf_bytes = build_participants_pdf(
        title=tournament.name,
        subtitle=subtitle,
        filter_summary=" · ".join(summary_parts),
        rows=rows,
        lang=lang,
    )

    slug = re.sub(r"[^A-Za-z0-9]+", "-", tournament.name).strip("-").lower() or "tournoi"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="participants-{slug}.pdf"'},
    )


@router.get(
    "/tournaments/{tournament_id}/participants",
    response_model=list[schemas.ParticipantRead],
)
def list_participants(
    tournament_id: uuid.UUID,
    session: Session = Depends(db_session),
    _: Principal = Depends(current_principal),
) -> list[schemas.ParticipantRead]:
    _require_tournament(session, tournament_id)
    groups = {g.id: g.name for g in crud.get_groups_by_tournament(session, tournament_id)}
    return [
        participant_read(session, p, group_name=groups.get(p.group_id))
        for p in crud.get_participants_by_tournament(session, tournament_id)
    ]


@router.post(
    "/tournaments/{tournament_id}/participants",
    response_model=list[schemas.ParticipantRead],
    status_code=status.HTTP_201_CREATED,
)
def register_participants(
    tournament_id: uuid.UUID,
    body: schemas.RegisterParticipants,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[schemas.ParticipantRead]:
    _require_tournament(session, tournament_id)
    _assert_inscription_access(principal, tournament_id)
    existing = {p.member_id for p in crud.get_participants_by_tournament(session, tournament_id)}
    to_add = [mid for mid in body.member_ids if mid not in existing]
    created = register_members_for_tournament(session, tournament_id, to_add)
    return [participant_read(session, p) for p in created]


@router.get(
    "/tournaments/{tournament_id}/registration",
    response_model=list[schemas.RegistrationRow],
)
def registration_list(
    tournament_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> list[schemas.RegistrationRow]:
    """All members across clubs, flagged registered/not for this tournament."""
    tournament = _require_tournament(session, tournament_id)
    _assert_inscription_access(principal, tournament_id)
    club_names = {c.id: c.name for c in crud.get_all(session, Club)}
    registered = {p.member_id for p in crud.get_participants_by_tournament(session, tournament_id)}
    # A weight is "stale" if never recorded or older than the reweigh threshold.
    cutoff = _subtract_months(date.today(), tournament.reweigh_months)
    rows = [
        schemas.RegistrationRow(
            member_id=m.id,
            member_name=f"{m.first_name} {m.last_name}",
            first_name=m.first_name,
            last_name=m.last_name,
            club_name=club_names.get(m.club_id, "—"),
            gender=m.gender,
            weight=m.weight,
            registered=m.id in registered,
            weight_updated_at=m.weight_updated_at,
            weight_stale=m.weight_updated_at is None or m.weight_updated_at < cutoff,
        )
        for m in crud.get_all(session, Member)
    ]
    rows.sort(key=lambda r: r.member_name.lower())
    return rows


@router.delete(
    "/tournaments/{tournament_id}/participants/by-member/{member_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unregister_participant(
    tournament_id: uuid.UUID,
    member_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> None:
    _require_tournament(session, tournament_id)
    _assert_inscription_access(principal, tournament_id)
    if not unregister_member_from_tournament(session, tournament_id, member_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Member is not registered")


@router.get("/tournaments/{tournament_id}/groups", response_model=list[schemas.GroupRead])
def list_groups(
    tournament_id: uuid.UUID,
    session: Session = Depends(db_session),
    _: Principal = Depends(current_principal),
) -> list[schemas.GroupRead]:
    _require_tournament(session, tournament_id)
    participants = crud.get_participants_by_tournament(session, tournament_id)
    members = {p.member_id: crud.get_by_id(session, Member, p.member_id) for p in participants}
    groups = crud.get_groups_by_tournament(session, tournament_id)
    out: list[schemas.GroupRead] = []
    for g in groups:
        g_parts = [
            participant_read(session, p, member=members.get(p.member_id), group_name=g.name)
            for p in participants
            if p.group_id == g.id
        ]
        out.append(
            schemas.GroupRead(
                id=g.id, name=g.name, tournament_id=g.tournament_id, participants=g_parts
            )
        )
    return out


@router.post(
    "/tournaments/{tournament_id}/groups/generate",
    response_model=list[schemas.GroupRead],
    status_code=status.HTTP_201_CREATED,
)
def generate_groups(
    tournament_id: uuid.UUID,
    body: schemas.GroupConfig,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> list[schemas.GroupRead]:
    _require_tournament(session, tournament_id)
    if crud.get_groups_by_tournament(session, tournament_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Groups already generated")
    config = GAConfig(
        max_group_size=body.max_group_size,
        max_additional_groups=body.max_additional_groups,
        small_swaps=3,
        big_swaps=1,
        population_size=50,
        generations=100,
        mutation_rate=0.4,
        scores_weights=_DEFAULT_WEIGHTS,
    )
    try:
        setup_tournament_groups(session, tournament_id, config)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return list_groups(tournament_id, session, _)


@router.put(
    "/tournaments/{tournament_id}/groups/{group_id}/participants",
    response_model=list[schemas.GroupRead],
)
def edit_group_participants(
    tournament_id: uuid.UUID,
    group_id: uuid.UUID,
    body: schemas.SetGroupParticipants,
    session: Session = Depends(db_session),
    _: Principal = Depends(require_roles("admin")),
) -> list[schemas.GroupRead]:
    """Replace a group's members (matches are reconciled, scores preserved)."""
    _require_tournament(session, tournament_id)
    group = crud.get_by_id(session, Group, group_id)
    if group is None or group.tournament_id != tournament_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found in this tournament")
    try:
        set_group_participants(session, group_id, body.participant_ids)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    # Return every group — a move can change another group too.
    return list_groups(tournament_id, session, _)
