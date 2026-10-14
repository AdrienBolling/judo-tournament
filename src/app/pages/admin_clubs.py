"""Admin page — club overview, coach management."""

import streamlit as st

from backend.auth import hash_password
from backend.database import crud
from backend.database.database import get_session
from backend.database.models import Club, Coach, Member

st.title("Clubs & Coaches")

session = get_session()

try:
    # ------------------------------------------------------------------
    # Create club
    # ------------------------------------------------------------------

    with st.expander("Create new club"):
        col1, col2 = st.columns(2)
        club_name = col1.text_input("Club name", key="nc_name")
        club_loc = col2.text_input("Location", key="nc_loc")
        if st.button("Create club"):
            if club_name:
                crud.create(session, Club(name=club_name, location=club_loc))
                st.rerun()

    # ------------------------------------------------------------------
    # Club selector
    # ------------------------------------------------------------------

    clubs = crud.get_all(session, Club)
    if not clubs:
        st.info("No clubs yet — create one above.")
        st.stop()

    selected_club = st.selectbox(
        "Select club",
        clubs,
        format_func=lambda c: f"{c.name} ({c.location})",
    )
    cid = selected_club.id

    st.divider()

    tab_overview, tab_coaches, tab_members = st.tabs(["Overview", "Coaches", "Members"])

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    with tab_overview:
        coaches = crud.get_coaches_by_club(session, cid)
        members = crud.get_members_by_club(session, cid)

        col1, col2 = st.columns(2)
        col1.metric("Coaches", len(coaches))
        col2.metric("Members", len(members))

        if coaches:
            st.markdown("**Coaches**")
            for c in coaches:
                st.write(f"- {c.first_name} {c.last_name} — {c.email}")

        if members:
            st.markdown("**Members**")
            rows = [
                {
                    "Name": f"{m.first_name} {m.last_name}",
                    "Gender": m.gender,
                    "Weight (kg)": m.weight,
                    "Category": m.age_category,
                }
                for m in members
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # Coaches — add / remove
    # ------------------------------------------------------------------

    with tab_coaches:
        coaches = crud.get_coaches_by_club(session, cid)

        # List existing coaches with remove button
        if coaches:
            for coach in coaches:
                col_info, col_btn = st.columns([4, 1])
                col_info.write(
                    f"**{coach.first_name} {coach.last_name}** — "
                    f"{coach.email} / {coach.phone_number}"
                )
                if col_btn.button("Remove", key=f"rm_coach_{coach.id}"):
                    crud.delete(session, coach)
                    st.rerun()
        else:
            st.info("No coaches for this club.")

        # Add coach form
        st.subheader("Add coach")
        col1, col2 = st.columns(2)
        with col1:
            co_fn = st.text_input("First name", key="ac_fn")
            co_ln = st.text_input("Last name", key="ac_ln")
            co_email = st.text_input("Email", key="ac_email")
        with col2:
            co_phone = st.text_input("Phone", key="ac_phone")
            co_pwd = st.text_input("Password", type="password", key="ac_pwd")

        if st.button("Add coach"):
            if co_fn and co_ln and co_email and co_pwd:
                crud.create(
                    session,
                    Coach(
                        first_name=co_fn.strip(),
                        last_name=co_ln.strip(),
                        email=co_email.strip(),
                        phone_number=co_phone.strip() if co_phone else "",
                        club_id=cid,
                        password_hash=hash_password(co_pwd),
                    ),
                )
                st.rerun()
            else:
                st.warning("First name, last name, email and password are required.")

    # ------------------------------------------------------------------
    # Members — read-only view (managed by coaches via their own page)
    # ------------------------------------------------------------------

    with tab_members:
        members = crud.get_members_by_club(session, cid)
        if members:
            rows = [
                {
                    "Last name": m.last_name,
                    "First name": m.first_name,
                    "Gender": m.gender,
                    "Weight (kg)": m.weight,
                    "Date of birth": str(m.date_of_birth),
                    "Category": m.age_category,
                }
                for m in members
            ]
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("No members in this club yet.")

except Exception:
    session.close()
    raise
else:
    session.close()
