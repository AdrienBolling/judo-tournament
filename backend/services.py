from __future__ import annotations

import csv
import io
from typing import TypedDict

from sqlmodel import Session, delete, select

from .models import GroupMembership, MatchResult, Participant, TournamentGroup

CSV_COLUMNS = ["last_name", "first_name", "club", "sex", "age_category", "weight"]


class GroupPayload(TypedDict, total=False):
    name: str
    sex: str
    age_category: str
    participant_ids: list[int | str]


def import_participants_csv(session: Session, file_bytes: bytes, replace_existing: bool = True) -> int:
    if replace_existing:
        session.exec(delete(MatchResult))
        session.exec(delete(GroupMembership))
        session.exec(delete(TournamentGroup))
        session.exec(delete(Participant))
        session.commit()

    text = file_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), skipinitialspace=True)
    normalized_fieldnames = [name.strip() for name in (reader.fieldnames or [])]
    if normalized_fieldnames != CSV_COLUMNS:
        raise ValueError(f"Invalid CSV columns. Expected: {', '.join(CSV_COLUMNS)}")

    created = 0
    for row_idx, row in enumerate(reader, start=2):
        try:
            weight = float(row["weight"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid weight at CSV row {row_idx}: {row['weight']!r}") from exc

        participant = Participant(
            last_name=row["last_name"].strip(),
            first_name=row["first_name"].strip(),
            club=row["club"].strip(),
            sex=row["sex"].strip(),
            age_category=row["age_category"].strip(),
            weight=weight,
        )
        session.add(participant)
        created += 1

    session.commit()
    return created


def get_filtered_participants(
    session: Session,
    *,
    sex: str | None = None,
    age_category: str | None = None,
    club: str | None = None,
    name_query: str | None = None,
) -> list[Participant]:
    statement = select(Participant)
    if sex:
        statement = statement.where(Participant.sex == sex)
    if age_category:
        statement = statement.where(Participant.age_category == age_category)
    if club:
        statement = statement.where(Participant.club == club)
    if name_query:
        q = f"%{name_query.strip().lower()}%"
        statement = statement.where(
            Participant.first_name.ilike(q) | Participant.last_name.ilike(q)
        )
    return list(session.exec(statement.order_by(Participant.last_name, Participant.first_name)))


def list_unique_values(session: Session, field_name: str) -> list[str]:
    field = getattr(Participant, field_name)
    statement = select(field).distinct().order_by(field)
    return [v for v in session.exec(statement) if v is not None]


def get_draft_participant_order(session: Session) -> list[int]:
    participants = list(session.exec(select(Participant).order_by(Participant.weight)))
    return [p.id for p in participants if p.id is not None]


def set_groups(session: Session, groups: list[GroupPayload]) -> None:
    session.exec(delete(GroupMembership))
    session.exec(delete(TournamentGroup))
    session.commit()

    for group_payload in groups:
        group = TournamentGroup(
            name=group_payload["name"],
            sex=group_payload.get("sex"),
            age_category=group_payload.get("age_category"),
        )
        session.add(group)
        session.flush()
        for participant_id in group_payload.get("participant_ids", []):
            session.add(GroupMembership(group_id=group.id, participant_id=int(participant_id)))
    session.commit()


def list_groups_with_participants(session: Session) -> list[dict]:
    groups = list(session.exec(select(TournamentGroup).order_by(TournamentGroup.name)))
    output = []
    for group in groups:
        memberships = list(
            session.exec(
                select(GroupMembership).where(GroupMembership.group_id == group.id)
            )
        )
        participant_ids = [m.participant_id for m in memberships]
        participants = []
        if participant_ids:
            participants = list(
                session.exec(
                    select(Participant).where(Participant.id.in_(participant_ids))
                )
            )
            participants.sort(key=lambda p: (p.last_name, p.first_name))
        output.append({"group": group, "participants": participants})
    return output


def save_match_result(
    session: Session,
    *,
    group_id: int,
    participant_a_id: int,
    participant_b_id: int,
    winner_id: int,
    notes: str = "",
) -> MatchResult:
    result = MatchResult(
        group_id=group_id,
        participant_a_id=participant_a_id,
        participant_b_id=participant_b_id,
        winner_id=winner_id,
        notes=notes,
    )
    session.add(result)
    session.commit()
    session.refresh(result)
    return result


def generate_results_report(session: Session) -> str:
    participants = {
        p.id: p for p in session.exec(select(Participant))
        if p.id is not None
    }
    groups = {g.id: g for g in session.exec(select(TournamentGroup)) if g.id is not None}
    def format_participant_name(participant_id: int) -> str:
        participant = participants.get(participant_id)
        if participant:
            return f"{participant.first_name} {participant.last_name}"
        return str(participant_id)

    lines: list[str] = ["Judo Tournament Results", "=======================", ""]
    for group_id, group in sorted(groups.items(), key=lambda x: x[1].name):
        lines.append(f"Group: {group.name}")
        group_results = list(
            session.exec(select(MatchResult).where(MatchResult.group_id == group_id))
        )
        if not group_results:
            lines.append("  No results recorded.")
            lines.append("")
            continue
        for r in group_results:
            a_name = format_participant_name(r.participant_a_id)
            b_name = format_participant_name(r.participant_b_id)
            w_name = format_participant_name(r.winner_id)
            lines.append(f"  {a_name} vs {b_name} -> Winner: {w_name}")
            if r.notes:
                lines.append(f"    Notes: {r.notes}")
        lines.append("")
    return "\n".join(lines)
