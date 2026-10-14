"""Aggregated results for a club across all its tournaments."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from backend.database import crud
from backend.scoring import compute_group_standings

from .. import schemas
from ..deps import current_principal, db_session
from ..security import Principal

router = APIRouter(tags=["results"])


@router.get("/clubs/{club_id}/results", response_model=schemas.ClubResults)
def club_results(
    club_id: uuid.UUID,
    session: Session = Depends(db_session),
    principal: Principal = Depends(current_principal),
) -> schemas.ClubResults:
    if principal.role == "coach" and principal.club_id != str(club_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed for this club")
    if principal.role not in ("admin", "coach"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")

    members = crud.get_members_by_club(session, club_id)
    member_map = {m.id: m for m in members}
    tournaments = crud.get_club_tournaments(session, club_id)

    total_wins = total_draws = total_losses = 0
    tournament_results: list[schemas.TournamentResult] = []

    for t in tournaments:
        participants = crud.get_participants_by_tournament(session, t.id)
        club_participants = [p for p in participants if p.member_id in member_map]
        if not club_participants:
            continue
        groups = {g.id: g for g in crud.get_groups_by_tournament(session, t.id)}

        member_rows: list[schemas.MemberResult] = []
        for p in club_participants:
            member = member_map[p.member_id]
            group = groups.get(p.group_id)
            matches = crud.get_matches_for_participant(session, p.id)
            completed = [m for m in matches if m.completed]
            wins = sum(1 for m in completed if m.winner_id == p.id)
            losses = sum(1 for m in completed if m.winner_id and m.winner_id != p.id)
            draws = sum(1 for m in completed if m.winner_id is None)
            total_wins += wins
            total_losses += losses
            total_draws += draws

            rank = group_size = None
            if group:
                rows = compute_group_standings(crud.get_matches_by_group(session, group.id))
                group_size = len(rows)
                rank = next(
                    (i + 1 for i, s in enumerate(rows) if s["participant_id"] == p.id), None
                )

            member_rows.append(
                schemas.MemberResult(
                    member_id=member.id,
                    member_name=f"{member.first_name} {member.last_name}",
                    group_label=group.name if group else "Unassigned",
                    wins=wins,
                    draws=draws,
                    losses=losses,
                    rank=rank,
                    group_size=group_size,
                )
            )

        tournament_results.append(
            schemas.TournamentResult(
                tournament_id=t.id,
                tournament_name=t.name,
                date=t.date,
                members=member_rows,
            )
        )

    return schemas.ClubResults(
        total_wins=total_wins,
        total_draws=total_draws,
        total_losses=total_losses,
        tournaments=tournament_results,
    )
