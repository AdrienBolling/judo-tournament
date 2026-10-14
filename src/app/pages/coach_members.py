"""Coach page — view and manage club members, CSV upload."""

import uuid
from datetime import date

import streamlit as st

from backend.database import crud
from backend.database.database import get_session
from backend.database.models import Club, Member
from backend.utils import import_members_from_csv

st.title("Club Members")

session = get_session()

try:
    # Determine which club to show
    role = st.session_state.get("role")
    if role == "admin":
        clubs = crud.get_all(session, Club)
        if not clubs:
            st.warning("No clubs exist yet.")
            st.stop()
        selected_club = st.selectbox("Select club", clubs, format_func=lambda c: c.name)
        club_id = selected_club.id
    else:
        club_id = uuid.UUID(st.session_state["club_id"])
        selected_club = crud.get_by_id(session, Club, club_id)
        st.subheader(selected_club.name if selected_club else "")

    # ------------------------------------------------------------------
    # Member list
    # ------------------------------------------------------------------

    members = crud.get_members_by_club(session, club_id)

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
        st.dataframe(rows, use_container_width=True)
    else:
        st.info("No members registered for this club.")

    # ------------------------------------------------------------------
    # Add single member
    # ------------------------------------------------------------------

    with st.expander("Add a member"):
        col1, col2 = st.columns(2)
        with col1:
            fn = st.text_input("First name", key="m_fn")
            ln = st.text_input("Last name", key="m_ln")
            dob = st.date_input(
                "Date of birth",
                value=date(2000, 1, 1),
                min_value=date(1930, 1, 1),
                max_value=date.today(),
                key="m_dob",
            )
        with col2:
            gender = st.selectbox("Gender", ["M", "F"], key="m_gender")
            weight = st.number_input("Weight (kg)", min_value=10.0, max_value=200.0, value=60.0, step=0.5, key="m_weight")

        if st.button("Add member"):
            if fn and ln:
                crud.create(
                    session,
                    Member(
                        first_name=fn.strip(), last_name=ln.strip(),
                        date_of_birth=dob, weight=weight,
                        gender=gender, club_id=club_id,
                    ),
                )
                st.rerun()

    # ------------------------------------------------------------------
    # CSV upload
    # ------------------------------------------------------------------

    with st.expander("Import members from CSV"):
        st.caption("Expected columns: `first_name, last_name, date_of_birth, weight, gender`")
        uploaded = st.file_uploader("Upload CSV", type=["csv"], key="csv_upload")
        if uploaded and st.button("Import"):
            # Save to a temp file so pandas can read it
            import tempfile
            from pathlib import Path
            tmp = Path(tempfile.mktemp(suffix=".csv"))
            tmp.write_bytes(uploaded.getvalue())
            try:
                imported = import_members_from_csv(session, tmp, club_id)
                st.success(f"Imported {len(imported)} members.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            finally:
                tmp.unlink(missing_ok=True)

finally:
    session.close()
