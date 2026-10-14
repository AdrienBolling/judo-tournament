"""Judo Tournament Manager — Streamlit entry-point."""

from pathlib import Path

import streamlit as st

from backend.auth import hash_password
from backend.database import crud
from backend.database.database import get_session, init_db
from backend.database.models import AdminUser

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

init_db()

_PAGES = Path(__file__).parent / "pages"

# ---------------------------------------------------------------------------
# First-run: create initial admin
# ---------------------------------------------------------------------------


def _first_run_setup():
    st.title("Judo Tournament Manager")
    st.info("No administrator account found. Create one to get started.")
    username = st.text_input("Admin username")
    password = st.text_input("Admin password", type="password")
    confirm = st.text_input("Confirm password", type="password")
    if st.button("Create admin account"):
        if not username or not password:
            st.error("Username and password are required.")
        elif password != confirm:
            st.error("Passwords do not match.")
        else:
            with get_session() as session:
                crud.create(
                    session,
                    AdminUser(username=username, password_hash=hash_password(password)),
                )
            st.success("Admin account created! Please reload the page.")
            st.rerun()


# ---------------------------------------------------------------------------
# Main routing
# ---------------------------------------------------------------------------

with get_session() as session:
    _admin_exists = len(crud.get_all(session, AdminUser)) > 0

if not _admin_exists:
    _first_run_setup()
elif not st.session_state.get("authenticated"):
    login_page = st.Page(str(_PAGES / "login.py"), title="Login")
    pg = st.navigation([login_page], position="hidden")
    pg.run()
else:
    role = st.session_state["role"]

    admin_pages = [
        st.Page(str(_PAGES / "admin_tournaments.py"), title="Tournaments"),
        st.Page(str(_PAGES / "admin_clubs.py"), title="Clubs & Coaches"),
    ]
    coach_pages = [
        st.Page(str(_PAGES / "coach_members.py"), title="Members"),
        st.Page(str(_PAGES / "coach_results.py"), title="Results"),
    ]
    referee_pages = [
        st.Page(str(_PAGES / "referee_scoring.py"), title="Scoring"),
    ]

    sections: dict[str, list] = {}
    if role == "admin":
        sections["Administration"] = admin_pages
        sections["Coaching"] = coach_pages
        sections["Refereeing"] = referee_pages
    elif role == "coach":
        sections["Coaching"] = coach_pages
    elif role == "referee":
        sections["Refereeing"] = referee_pages

    pg = st.navigation(sections)

    # Sidebar: show user info + logout
    with st.sidebar:
        st.caption(f"Logged in as **{st.session_state.get('display_name', role)}**")
        if st.button("Logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    pg.run()
