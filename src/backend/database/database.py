"""Database engine and session management."""

import os
from pathlib import Path

from sqlalchemy import event, text
from sqlmodel import Session, SQLModel, create_engine

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
# Override with JUDO_DB_PATH (absolute or relative to CWD) for deploys/tests.
_DEFAULT_DB_PATH = Path(os.environ.get("JUDO_DB_PATH", _PROJECT_ROOT / "judo_tournament.db"))


def get_engine(db_path: Path = _DEFAULT_DB_PATH):
    """Create a SQLite database engine."""
    eng = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return eng


engine = get_engine()


# Columns added after the initial schema. ``create_all`` only creates missing
# *tables*, never alters existing ones, so we add these by hand for SQLite DBs
# that predate them. Each entry: (table, column, column definition).
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("tournament", "status", "VARCHAR DEFAULT 'closed' NOT NULL"),
    ("tournament", "reweigh_months", "INTEGER DEFAULT 3 NOT NULL"),
    ("refereetoken", "role", "VARCHAR DEFAULT 'referee' NOT NULL"),
    ("member", "weight_updated_at", "DATE"),
]


def _ensure_columns() -> None:
    """Idempotently add new columns to pre-existing SQLite tables."""
    with engine.begin() as conn:
        for table, column, ddl in _ADDED_COLUMNS:
            existing = {row[1] for row in conn.execute(text(f'PRAGMA table_info("{table}")'))}
            if not existing:
                continue  # table doesn't exist yet — create_all will build it fresh
            if column not in existing:
                conn.execute(text(f'ALTER TABLE "{table}" ADD COLUMN {column} {ddl}'))


def _relax_member_nullability() -> None:
    """Drop the NOT NULL constraint on member.weight / date_of_birth.

    These columns were originally NOT NULL; members can now be created with just
    a name + gender. SQLite can't drop NOT NULL in place, so rebuild the table
    (preserving all rows) when an older schema is detected.
    """
    with engine.connect() as conn:
        info = list(conn.execute(text('PRAGMA table_info("member")')))
    if not info:
        return  # fresh DB — create_all already made them nullable
    notnull = {row[1]: row[3] for row in info}
    if not (notnull.get("date_of_birth") or notnull.get("weight")):
        return  # already relaxed

    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("PRAGMA foreign_keys=OFF")
        cur.executescript(
            """
            CREATE TABLE member_new (
                id CHAR(32) NOT NULL,
                last_name VARCHAR NOT NULL,
                first_name VARCHAR NOT NULL,
                date_of_birth DATE,
                weight FLOAT,
                gender VARCHAR NOT NULL,
                club_id CHAR(32) NOT NULL,
                weight_updated_at DATE,
                PRIMARY KEY (id),
                FOREIGN KEY(club_id) REFERENCES club (id)
            );
            INSERT INTO member_new
                (id, last_name, first_name, date_of_birth, weight, gender, club_id, weight_updated_at)
                SELECT id, last_name, first_name, date_of_birth, weight, gender, club_id, weight_updated_at
                FROM member;
            DROP TABLE member;
            ALTER TABLE member_new RENAME TO member;
            """
        )
        cur.execute("PRAGMA foreign_keys=ON")
        raw.commit()
    finally:
        raw.close()


def init_db() -> None:
    """Create all tables defined in SQLModel metadata, then patch new columns."""
    # Import models so they are registered with SQLModel.metadata
    import backend.database.models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _ensure_columns()
    _relax_member_nullability()


def get_session() -> Session:
    """Get a new database session."""
    return Session(engine)
