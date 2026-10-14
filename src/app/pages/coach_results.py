"""Coach page — view member results and aggregated club statistics."""

import uuid

import streamlit as st

from backend.database import crud
from backend.database.database import get_session
from backend.database.models import Club, Member
from backend.scoring import compute_group_standings

st.title("Results")

session = get_session()

try:
    role = st.session_state.get("role")
    if role == "admin":
        clubs = crud.get_all(session, Club)
        if not clubs:
            st.info("No clubs yet.")
            st.stop()
        selected_club = st.selectbox("Select club", clubs, format_func=lambda c: c.name)
        club_id = selected_club.id
    else:
        club_id = uuid.UUID(st.session_state["club_id"])

    # ------------------------------------------------------------------
    # Tournaments this club participated in
    # ------------------------------------------------------------------

    tournaments = crud.get_club_tournaments(session, club_id)
    members = crud.get_members_by_club(session, club_id)
    member_map = {m.id: m for m in members}

    if not tournaments:
        st.info("This club has not participated in any tournament yet.")
        st.stop()

    # ------------------------------------------------------------------
    # Aggregated stats across all tournaments
    # ------------------------------------------------------------------

    total_wins, total_losses, total_draws = 0, 0, 0

    for t in tournaments:
        with st.expander(f"{t.name} — {t.date}"):
            participants = crud.get_participants_by_tournament(session, t.id)
            club_participants = [p for p in participants if p.member_id in member_map]

            if not club_participants:
                st.write("No members from this club in this tournament.")
                continue

            groups = crud.get_groups_by_tournament(session, t.id)

            for p in club_participants:
                member = member_map[p.member_id]
                group = next((g for g in groups if g.id == p.group_id), None)
                group_label = group.name if group else "Unassigned"

                matches = crud.get_matches_for_participant(session, p.id)
                completed = [m for m in matches if m.completed]
                wins = sum(1 for m in completed if m.winner_id == p.id)
                losses = sum(1 for m in completed if m.winner_id and m.winner_id != p.id)
                draws = sum(1 for m in completed if m.winner_id is None)

                total_wins += wins
                total_losses += losses
                total_draws += draws

                st.write(
                    f"**{member.first_name} {member.last_name}** "
                    f"({group_label}) — "
                    f"{wins}W / {draws}D / {losses}L"
                )

                # Show group standing if group exists
                if group:
                    all_group_matches = crud.get_matches_by_group(session, group.id)
                    standings = compute_group_standings(all_group_matches)
                    rank = next(
                        (i + 1 for i, s in enumerate(standings) if s["participant_id"] == p.id),
                        None,
                    )
                    if rank:
                        st.caption(f"Group rank: **{rank}** / {len(standings)}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    st.divider()
    st.subheader("Club totals")
    col1, col2, col3 = st.columns(3)
    col1.metric("Wins", total_wins)
    col2.metric("Draws", total_draws)
    col3.metric("Losses", total_losses)

finally:
    session.close()
