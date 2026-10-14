"""Backend utilities — bulk import, data helpers."""

import uuid
from pathlib import Path

import pandas as pd
from sqlmodel import Session

from backend.database import crud
from backend.database.models import Member


def import_members_from_csv(
    session: Session,
    csv_path: str | Path,
    club_id: uuid.UUID,
) -> list[Member]:
    """Bulk-import club members from a CSV file.

    Expected CSV columns::

        first_name, last_name, date_of_birth, weight, gender

    ``date_of_birth`` is parsed with *dayfirst=True* so both
    ``DD/MM/YYYY`` and ``YYYY-MM-DD`` formats are accepted.

    Returns the list of created ``Member`` objects (already committed).
    """
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    required = {"first_name", "last_name", "date_of_birth", "weight", "gender"}
    missing = required - set(df.columns)
    if missing:
        msg = f"Missing CSV columns: {missing}"
        raise ValueError(msg)

    df["date_of_birth"] = pd.to_datetime(
        df["date_of_birth"], dayfirst=True, format="mixed"
    ).dt.date

    members = [
        Member(
            first_name=row["first_name"].strip(),
            last_name=row["last_name"].strip(),
            date_of_birth=row["date_of_birth"],
            weight=float(row["weight"]),
            gender=row["gender"].strip(),
            club_id=club_id,
        )
        for _, row in df.iterrows()
    ]

    return crud.create_all(session, members)
