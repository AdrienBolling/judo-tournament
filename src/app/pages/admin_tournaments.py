"""Admin page — tournament creation, participant registration, group generation, referee tokens."""

from datetime import date

import streamlit as st

from backend.auth import generate_referee_token
from backend.database import crud
from backend.database.database import get_session
from backend.database.models import (
    Club,
    Member,
    RefereeToken,
    Tournament,
)
from backend.solver.ga_solver import GAConfig
from backend.tournament import register_members_for_tournament, setup_tournament_groups


# ---------------------------------------------------------------------------
# Tournament detail (called from main body)
# ---------------------------------------------------------------------------

def _manage_tournament(session, tournament: Tournament):
    tid = tournament.id
    participants = crud.get_participants_by_tournament(session, tid)
    groups = crud.get_groups_by_tournament(session, tid)
    tokens = crud.get_referee_tokens_by_tournament(session, tid)

    tab_parts, tab_groups, tab_tokens = st.tabs(["Participants", "Groups", "Referee Tokens"])

    # --- Participants ---------------------------------------------------
    with tab_parts:
        st.write(f"**{len(participants)}** registered participants")
        if participants:
            rows = []
            for p in participants:
                member = crud.get_by_id(session, Member, p.member_id)
                if member:
                    group_name = next(
                        (g.name for g in groups if g.id == p.group_id), "—"
                    ) if p.group_id else "—"
                    rows.append({
                        "Name": f"{member.first_name} {member.last_name}",
                        "Gender": member.gender,
                        "Weight": member.weight,
                        "Category": member.age_category,
                        "Group": group_name,
                    })
            if rows:
                st.dataframe(rows, use_container_width=True, hide_index=True)

        st.subheader("Register participants")
        clubs = crud.get_all(session, Club)
        if clubs:
            reg_club = st.selectbox("From club", clubs, format_func=lambda c: c.name, key="reg_club")
            club_members = crud.get_members_by_club(session, reg_club.id)
            already = {p.member_id for p in participants}
            available = [m for m in club_members if m.id not in already]
            if available:
                selected = st.multiselect(
                    "Select members",
                    available,
                    format_func=lambda m: f"{m.first_name} {m.last_name} ({m.weight}kg, {m.gender})",
                )
                if st.button("Register selected") and selected:
                    register_members_for_tournament(session, tid, [m.id for m in selected])
                    st.rerun()
            else:
                st.info("All members from this club are already registered (or no members).")

    # --- Groups ---------------------------------------------------------
    with tab_groups:
        if groups:
            for g in groups:
                with st.container(border=True):
                    g_parts = [p for p in participants if p.group_id == g.id]
                    st.write(f"**{g.name}** — {len(g_parts)} participants")
                    for p in g_parts:
                        member = crud.get_by_id(session, Member, p.member_id)
                        if member:
                            st.write(
                                f"  - {member.first_name} {member.last_name} "
                                f"({member.weight}kg, {member.gender})"
                            )
        else:
            if len(participants) >= 2:
                st.subheader("Generate groups")
                max_size = st.slider("Max group size", 3, 6, 4, key="gs_max")
                extra = st.slider("Max additional groups", 0, 4, 2, key="gs_extra")
                if st.button("Generate groups (run solver)"):
                    config = GAConfig(
                        max_group_size=max_size,
                        max_additional_groups=extra,
                        small_swaps=3,
                        big_swaps=1,
                        population_size=50,
                        generations=100,
                        mutation_rate=0.4,
                        scores_weights={
                            "gender": 1.0, "weight": 3.0,
                            "club": 1.0, "group_size": 0.5, "nb_groups": 0.5,
                        },
                    )
                    with st.spinner("Running group solver..."):
                        setup_tournament_groups(session, tid, config)
                    st.rerun()
            else:
                st.info("Register at least 2 participants before generating groups.")

    # --- Referee tokens -------------------------------------------------
    with tab_tokens:
        if tokens:
            for tk in tokens:
                st.code(f"{tk.label}: {tk.token}", language=None)
        label = st.text_input("Token label (e.g. Table 1)", key="tk_label")
        if st.button("Generate referee token"):
            if label:
                crud.create(
                    session,
                    RefereeToken(
                        token=generate_referee_token(),
                        label=label,
                        tournament_id=tid,
                    ),
                )
                st.rerun()


# ---------------------------------------------------------------------------
# Page body
# ---------------------------------------------------------------------------

st.title("Tournament Management")

session = get_session()

try:
    # --- Create tournament ----------------------------------------------
    with st.expander("Create New Tournament"):
        clubs = crud.get_all(session, Club)
        if not clubs:
            st.warning("Create at least one club before creating a tournament.")
        else:
            t_name = st.text_input("Tournament name", key="t_name")
            t_date = st.date_input("Date", value=date.today(), key="t_date")
            t_loc = st.text_input("Location", key="t_loc")
            t_club = st.selectbox("Hosting club", clubs, format_func=lambda c: c.name, key="t_club")
            if st.button("Create tournament"):
                if t_name:
                    crud.create(
                        session,
                        Tournament(
                            name=t_name, date=t_date,
                            location=t_loc, hosting_club_id=t_club.id,
                        ),
                    )
                    st.rerun()

    # --- Select & manage tournament -------------------------------------
    st.divider()
    tournaments = crud.get_tournaments(session)

    if not tournaments:
        st.info("No tournaments yet.")
    else:
        selected_t = st.selectbox(
            "Select tournament to manage",
            tournaments,
            format_func=lambda t: f"{t.name} — {t.date}",
        )
        if selected_t:
            _manage_tournament(session, selected_t)

except Exception:
    session.close()
    raise
else:
    session.close()
