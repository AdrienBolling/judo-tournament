"""End-to-end API tests for tournament status, tokens, inscription & registration."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api import deps
from api.main import app


@pytest.fixture()
def client():
    """TestClient backed by a fresh in-memory DB (shared single connection)."""
    engine = create_engine(
        "sqlite://",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[deps.db_session] = _session
    yield TestClient(app)
    app.dependency_overrides.clear()


def _admin_headers(client) -> dict:
    tok = client.post("/api/setup/admin", json={"username": "a", "password": "a"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def _seed_tournament(client, headers) -> tuple[str, str, list[str]]:
    """Create a club, a few members and a tournament. Returns (tid, club_id, member_ids)."""
    club = client.post("/api/clubs", json={"name": "Lyon", "location": "Lyon"}, headers=headers).json()
    member_ids = []
    for i in range(3):
        m = client.post(
            f"/api/clubs/{club['id']}/members",
            json={
                "first_name": f"M{i}",
                "last_name": f"N{i}",
                "date_of_birth": "2000-01-01",
                "weight": 60 + i,
                "gender": "M" if i % 2 else "F",
            },
            headers=headers,
        ).json()
        member_ids.append(m["id"])
    t = client.post(
        "/api/tournaments",
        json={"name": "Open", "date": "2025-01-01", "location": "Lyon", "hosting_club_id": club["id"]},
        headers=headers,
    ).json()
    return t["id"], club["id"], member_ids


# ---------------------------------------------------------------------------
# Tournament status + public listing
# ---------------------------------------------------------------------------

def test_tournament_defaults_closed_and_opens(client):
    h = _admin_headers(client)
    tid, _, _ = _seed_tournament(client, h)
    assert client.get(f"/api/tournaments/{tid}", headers=h).json()["status"] == "closed"
    # Not in public open list while closed.
    assert client.get("/api/public/open-tournaments").json() == []
    # Open it.
    r = client.patch(f"/api/tournaments/{tid}/status", json={"status": "open"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "open"
    pub = client.get("/api/public/open-tournaments").json()
    assert [t["id"] for t in pub] == [tid]


def test_status_validation(client):
    h = _admin_headers(client)
    tid, _, _ = _seed_tournament(client, h)
    assert client.patch(f"/api/tournaments/{tid}/status", json={"status": "nope"}, headers=h).status_code == 400


# ---------------------------------------------------------------------------
# Custom / editable tokens + roles
# ---------------------------------------------------------------------------

def test_token_custom_value_role_and_update(client):
    h = _admin_headers(client)
    tid, _, _ = _seed_tournament(client, h)
    # Custom referee token.
    r = client.post(f"/api/tournaments/{tid}/tokens", json={"label": "Table 1", "token": "REF-1"}, headers=h)
    assert r.status_code == 201 and r.json()["token"] == "REF-1" and r.json()["role"] == "referee"
    ref_id = r.json()["id"]
    # Inscription token.
    insc = client.post(
        f"/api/tournaments/{tid}/tokens",
        json={"label": "Desk", "token": "INS-1", "role": "inscription"},
        headers=h,
    ).json()
    assert insc["role"] == "inscription"
    # Duplicate value rejected.
    assert client.post(f"/api/tournaments/{tid}/tokens", json={"label": "x", "token": "REF-1"}, headers=h).status_code == 409
    # Update value.
    upd = client.put(f"/api/tournaments/{tid}/tokens/{ref_id}", json={"token": "REF-2"}, headers=h)
    assert upd.status_code == 200 and upd.json()["token"] == "REF-2"
    # Updating to an existing value conflicts.
    assert client.put(f"/api/tournaments/{tid}/tokens/{ref_id}", json={"token": "INS-1"}, headers=h).status_code == 409


# ---------------------------------------------------------------------------
# Referee / inscription login (role + tournament match)
# ---------------------------------------------------------------------------

def test_login_role_enforced_and_tournament_match(client):
    h = _admin_headers(client)
    tid, _, _ = _seed_tournament(client, h)
    client.post(f"/api/tournaments/{tid}/tokens", json={"label": "R", "token": "REF", "role": "referee"}, headers=h)
    client.post(f"/api/tournaments/{tid}/tokens", json={"label": "I", "token": "INS", "role": "inscription"}, headers=h)

    # Referee token works for referee login, inscription token does not.
    assert client.post("/api/auth/login/referee", json={"token": "REF"}).status_code == 200
    assert client.post("/api/auth/login/referee", json={"token": "INS"}).status_code == 401
    # Inscription login mirrors.
    r = client.post("/api/auth/login/inscription", json={"token": "INS"})
    assert r.status_code == 200 and r.json()["role"] == "inscription" and r.json()["tournament_id"] == tid
    assert client.post("/api/auth/login/inscription", json={"token": "REF"}).status_code == 401
    # Tournament mismatch rejected.
    other = uuid.uuid4()
    assert client.post("/api/auth/login/referee", json={"token": "REF", "tournament_id": str(other)}).status_code == 401


# ---------------------------------------------------------------------------
# Registration desk
# ---------------------------------------------------------------------------

def test_registration_list_register_unregister(client):
    h = _admin_headers(client)
    tid, _, member_ids = _seed_tournament(client, h)

    rows = client.get(f"/api/tournaments/{tid}/registration", headers=h).json()
    assert len(rows) == 3 and all(r["registered"] is False for r in rows)

    # Register two.
    client.post(f"/api/tournaments/{tid}/participants", json={"member_ids": member_ids[:2]}, headers=h)
    rows = {r["member_id"]: r["registered"] for r in client.get(f"/api/tournaments/{tid}/registration", headers=h).json()}
    assert rows[member_ids[0]] and rows[member_ids[1]] and not rows[member_ids[2]]

    # Unregister one.
    assert client.delete(f"/api/tournaments/{tid}/participants/by-member/{member_ids[0]}", headers=h).status_code == 204
    rows = {r["member_id"]: r["registered"] for r in client.get(f"/api/tournaments/{tid}/registration", headers=h).json()}
    assert not rows[member_ids[0]] and rows[member_ids[1]]
    # Unregistering a non-participant 404s.
    assert client.delete(f"/api/tournaments/{tid}/participants/by-member/{member_ids[0]}", headers=h).status_code == 404


def test_inscription_role_scoped_access(client):
    h = _admin_headers(client)
    tid, _, member_ids = _seed_tournament(client, h)
    client.patch(f"/api/tournaments/{tid}/status", json={"status": "open"}, headers=h)
    client.post(f"/api/tournaments/{tid}/tokens", json={"label": "I", "token": "INS", "role": "inscription"}, headers=h)
    insc_tok = client.post("/api/auth/login/inscription", json={"token": "INS"}).json()["access_token"]
    ih = {"Authorization": f"Bearer {insc_tok}"}

    # Inscription staff can manage registration on their tournament.
    assert client.get(f"/api/tournaments/{tid}/registration", headers=ih).status_code == 200
    assert client.post(f"/api/tournaments/{tid}/participants", json={"member_ids": [member_ids[0]]}, headers=ih).status_code == 201
    # But not another tournament.
    other_tid, _, _ = _seed_tournament(client, h)
    assert client.get(f"/api/tournaments/{other_tid}/registration", headers=ih).status_code == 403


# ---------------------------------------------------------------------------
# PDF still renders
# ---------------------------------------------------------------------------

def test_member_edit_stamps_weight_and_staleness(client):
    h = _admin_headers(client)
    tid, club_id, member_ids = _seed_tournament(client, h)
    mid = member_ids[0]

    # Fresh member (created today) is not stale at the default 3-month threshold.
    rows = {r["member_id"]: r for r in client.get(f"/api/tournaments/{tid}/registration", headers=h).json()}
    assert rows[mid]["weight_stale"] is False
    assert rows[mid]["weight_updated_at"] is not None

    # Backdate the weigh-in well beyond the threshold → stale.
    from datetime import date

    from sqlmodel import Session

    # Reach the same engine the client uses via the override.
    gen = app.dependency_overrides[deps.db_session]()
    session: Session = next(gen)
    try:
        from backend.database import crud
        from backend.database.models import Member

        m = crud.get_by_id(session, Member, __import__("uuid").UUID(mid))
        crud.update(session, m, weight_updated_at=date(2000, 1, 1))
    finally:
        gen.close()

    rows = {r["member_id"]: r for r in client.get(f"/api/tournaments/{tid}/registration", headers=h).json()}
    assert rows[mid]["weight_stale"] is True

    # Editing the weight re-stamps the weigh-in date → no longer stale.
    upd = client.patch(f"/api/members/{mid}", json={"weight": 64.0}, headers=h)
    assert upd.status_code == 200 and upd.json()["weight"] == 64.0
    rows = {r["member_id"]: r for r in client.get(f"/api/tournaments/{tid}/registration", headers=h).json()}
    assert rows[mid]["weight_stale"] is False


def test_reweigh_months_setting(client):
    h = _admin_headers(client)
    tid, _, _ = _seed_tournament(client, h)
    assert client.get(f"/api/tournaments/{tid}", headers=h).json()["reweigh_months"] == 3
    r = client.patch(f"/api/tournaments/{tid}/settings", json={"reweigh_months": 6}, headers=h)
    assert r.status_code == 200 and r.json()["reweigh_months"] == 6
    assert client.patch(f"/api/tournaments/{tid}/settings", json={"reweigh_months": 0}, headers=h).status_code == 400


def test_minimal_member_create_and_completeness(client):
    h = _admin_headers(client)
    club = client.post("/api/clubs", json={"name": "Lyon", "location": "Lyon"}, headers=h).json()

    # Create with only first/last/gender — weight & DOB omitted.
    r = client.post(
        f"/api/clubs/{club['id']}/members",
        json={"first_name": "Min", "last_name": "Imal", "gender": "M"},
        headers=h,
    )
    assert r.status_code == 201
    m = r.json()
    assert m["weight"] is None and m["date_of_birth"] is None
    assert m["age"] is None and m["age_category"] == ""
    assert m["is_complete"] is False and m["weight_updated_at"] is None

    # Fill the missing info via edit → now complete, weigh-in stamped.
    upd = client.patch(
        f"/api/members/{m['id']}",
        json={"weight": 55.0, "date_of_birth": "2002-04-01"},
        headers=h,
    ).json()
    assert upd["is_complete"] is True and upd["weight_updated_at"] is not None
    assert upd["age_category"] != ""


def test_group_generation_blocked_when_weight_missing(client):
    h = _admin_headers(client)
    club = client.post("/api/clubs", json={"name": "Lyon", "location": "Lyon"}, headers=h).json()
    ids = []
    for i in range(2):
        mm = client.post(
            f"/api/clubs/{club['id']}/members",
            json={"first_name": f"N{i}", "last_name": "X", "gender": "M"},
            headers=h,
        ).json()
        ids.append(mm["id"])
    t = client.post(
        "/api/tournaments",
        json={"name": "T", "date": "2025-01-01", "location": "L", "hosting_club_id": club["id"]},
        headers=h,
    ).json()
    client.post(f"/api/tournaments/{t['id']}/participants", json={"member_ids": ids}, headers=h)
    r = client.post(
        f"/api/tournaments/{t['id']}/groups/generate",
        json={"max_group_size": 4, "max_additional_groups": 0},
        headers=h,
    )
    assert r.status_code == 400 and "missing a weight" in r.json()["detail"]


def test_participants_pdf_renders(client):
    h = _admin_headers(client)
    tid, _, member_ids = _seed_tournament(client, h)
    client.post(f"/api/tournaments/{tid}/participants", json={"member_ids": member_ids}, headers=h)
    r = client.get(f"/api/tournaments/{tid}/participants.pdf", headers=h)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"
