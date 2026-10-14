"""High-level tournament management operations."""

from __future__ import annotations

import uuid
from itertools import combinations

from sqlmodel import Session

from backend.database import crud
from backend.database.models import Group, Match, Member, Participant
from backend.scoring import generate_round_robin_matches
from backend.solver.ga_solver import GAConfig, GAGroupSolver


def setup_tournament_groups(
    session: Session,
    tournament_id: uuid.UUID,
    config: GAConfig,
) -> list[Group]:
    """Run the GA solver, create groups, assign participants, generate matches.

    Returns the list of newly created ``Group`` objects.
    """
    participants = crud.get_participants_by_tournament(session, tournament_id)
    if len(participants) < 2:
        msg = "Need at least 2 participants to generate groups."
        raise ValueError(msg)

    # Build member list and a mapping back to their Participant row
    members: list[Member] = []
    participant_by_member: dict[uuid.UUID, Participant] = {}
    for p in participants:
        member = crud.get_by_id(session, Member, p.member_id)
        members.append(member)
        participant_by_member[member.id] = p

    # The solver needs every participant's weight; reject incomplete members
    # with a clear message rather than producing NaN scores.
    missing = [f"{m.first_name} {m.last_name}" for m in members if m.weight is None]
    if missing:
        msg = "These participants are missing a weight: " + ", ".join(missing)
        raise ValueError(msg)

    # Solve
    solver = GAGroupSolver(config)
    result = solver.solve(members)

    # Persist groups, assignments, and matches
    created_groups: list[Group] = []
    for group_name, group_members in result.items():
        group = crud.create(session, Group(name=group_name, tournament_id=tournament_id))
        created_groups.append(group)

        group_participant_ids: list[uuid.UUID] = []
        for m in group_members:
            p = participant_by_member[m.id]
            crud.update(session, p, group_id=group.id)
            group_participant_ids.append(p.id)

        matches = generate_round_robin_matches(group.id, group_participant_ids)
        crud.create_all(session, matches)

    return created_groups


def set_group_participants(
    session: Session,
    group_id: uuid.UUID,
    participant_ids: list[uuid.UUID],
) -> Group:
    """Replace a group's membership with *participant_ids* and reconcile matches.

    Participants moving in from another group are removed from it; participants
    dropped from this group become unassigned. Round-robin matches are
    reconciled rather than rebuilt: existing matches between two members that
    both remain are kept (preserving their scores); matches involving a removed
    member are deleted; missing pairings are created.

    Raises ``ValueError`` if the group is unknown or an id does not belong to
    the group's tournament.
    """
    group = crud.get_by_id(session, Group, group_id)
    if group is None:
        msg = "Group not found."
        raise ValueError(msg)

    valid = {p.id: p for p in crud.get_participants_by_tournament(session, group.tournament_id)}
    unknown = [pid for pid in participant_ids if pid not in valid]
    if unknown:
        msg = f"Participants not registered for this tournament: {unknown}"
        raise ValueError(msg)

    new_set = set(participant_ids)
    current_set = {pid for pid, p in valid.items() if p.group_id == group_id}

    # Drop removed participants → unassigned, and clear their matches here.
    for pid in current_set - new_set:
        crud.update(session, valid[pid], group_id=None)
        _delete_group_matches_for_participant(session, group_id, pid)

    # Pull added participants in, detaching them from any previous group.
    for pid in new_set - current_set:
        p = valid[pid]
        if p.group_id is not None and p.group_id != group_id:
            _delete_group_matches_for_participant(session, p.group_id, pid)
        crud.update(session, p, group_id=group_id)

    session.commit()

    _ensure_round_robin_matches(session, group_id, list(new_set))
    session.refresh(group)
    return group


def _delete_group_matches_for_participant(
    session: Session, group_id: uuid.UUID, participant_id: uuid.UUID
) -> None:
    """Delete matches in *group_id* that involve *participant_id*."""
    for m in crud.get_matches_by_group(session, group_id):
        if participant_id in (m.participant_a_id, m.participant_b_id):
            session.delete(m)
    session.commit()


def _ensure_round_robin_matches(
    session: Session, group_id: uuid.UUID, participant_ids: list[uuid.UUID]
) -> None:
    """Create any missing pairwise matches for the group (keeps existing ones)."""
    existing = crud.get_matches_by_group(session, group_id)
    existing_pairs = {
        frozenset((m.participant_a_id, m.participant_b_id)) for m in existing
    }
    new_matches = [
        Match(group_id=group_id, participant_a_id=a, participant_b_id=b)
        for a, b in combinations(participant_ids, 2)
        if frozenset((a, b)) not in existing_pairs
    ]
    if new_matches:
        crud.create_all(session, new_matches)


def register_members_for_tournament(
    session: Session,
    tournament_id: uuid.UUID,
    member_ids: list[uuid.UUID],
) -> list[Participant]:
    """Create Participant rows linking members to a tournament."""
    participants = [
        Participant(member_id=mid, tournament_id=tournament_id)
        for mid in member_ids
    ]
    return crud.create_all(session, participants)


def unregister_member_from_tournament(
    session: Session,
    tournament_id: uuid.UUID,
    member_id: uuid.UUID,
) -> bool:
    """Remove a member's participation in a tournament.

    Cleans up the participant's matches in any assigned group first, then
    deletes the Participant row. Returns False if the member wasn't registered.
    """
    participant = crud.get_participant_by_member(session, tournament_id, member_id)
    if participant is None:
        return False
    if participant.group_id is not None:
        _delete_group_matches_for_participant(session, participant.group_id, participant.id)
    crud.delete(session, participant)
    return True
