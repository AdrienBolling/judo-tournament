"""Login page — coach / admin / referee authentication."""

import streamlit as st

from backend.auth import verify_password
from backend.database import crud
from backend.database.database import get_session
from backend.database.models import AdminUser

st.title("Judo Tournament Manager")

tab_coach, tab_admin, tab_referee = st.tabs(["Coach", "Admin", "Referee"])

# ---------------------------------------------------------------------------
# Coach login
# ---------------------------------------------------------------------------

with tab_coach:
    st.subheader("Coach login")
    email = st.text_input("Email", key="c_email")
    password = st.text_input("Password", type="password", key="c_pwd")
    if st.button("Login", key="c_btn"):
        with get_session() as session:
            coach = crud.get_coach_by_email(session, email.strip())
            if coach and coach.password_hash and verify_password(password, coach.password_hash):
                st.session_state.authenticated = True
                st.session_state.role = "coach"
                st.session_state.user_id = str(coach.id)
                st.session_state.club_id = str(coach.club_id)
                st.session_state.display_name = f"{coach.first_name} {coach.last_name}"
                st.rerun()
            else:
                st.error("Invalid email or password.")

# ---------------------------------------------------------------------------
# Admin login
# ---------------------------------------------------------------------------

with tab_admin:
    st.subheader("Admin login")
    username = st.text_input("Username", key="a_user")
    a_password = st.text_input("Password", type="password", key="a_pwd")
    if st.button("Login", key="a_btn"):
        with get_session() as session:
            admin = crud.get_admin_by_username(session, username.strip())
            if admin and verify_password(a_password, admin.password_hash):
                st.session_state.authenticated = True
                st.session_state.role = "admin"
                st.session_state.user_id = str(admin.id)
                st.session_state.display_name = f"Admin ({admin.username})"
                st.rerun()
            else:
                st.error("Invalid credentials.")

# ---------------------------------------------------------------------------
# Referee token
# ---------------------------------------------------------------------------

with tab_referee:
    st.subheader("Referee access")
    token = st.text_input("Tournament token", key="r_token")
    if st.button("Enter", key="r_btn"):
        with get_session() as session:
            ref = crud.get_referee_token_by_value(session, token.strip())
            if ref:
                st.session_state.authenticated = True
                st.session_state.role = "referee"
                st.session_state.tournament_id = str(ref.tournament_id)
                st.session_state.display_name = f"Referee ({ref.label})"
                st.rerun()
            else:
                st.error("Invalid token.")
