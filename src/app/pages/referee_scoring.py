"""Referee page — live match scoring and group standings."""

import uuid

import streamlit as st

from backend.database import crud
from backend.database.database import get_session
from backend.database.models import Group, Match, Member, Tournament
from backend.scoring import compute_group_standings, determine_match_winner, is_instant_win

st.title("Match Scoring")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_match(session, match: Match):
    session.add(match)
    session.commit()
    st.rerun()


def _auto_complete(session, match: Match):
    """Save and auto-complete if ippon or 2 waza-ari."""
    if is_instant_win(match):
        match.winner_id = determine_match_winner(match)
        match.completed = True
    _save_match(session, match)


session = get_session()

try:
    role = st.session_state.get("role")

    # Determine tournament
    if role == "referee":
        tournament_id = uuid.UUID(st.session_state["tournament_id"])
        tournament = crud.get_by_id(session, Tournament, tournament_id)
    else:
        # Admin: pick tournament
        tournaments = crud.get_tournaments(session)
        if not tournaments:
            st.info("No tournaments yet.")
            st.stop()
        tournament = st.selectbox(
            "Tournament", tournaments,
            format_func=lambda t: f"{t.name} — {t.date}",
        )
        tournament_id = tournament.id

    st.subheader(tournament.name)

    groups = crud.get_groups_by_tournament(session, tournament_id)
    if not groups:
        st.info("No groups generated for this tournament yet.")
        st.stop()

    selected_group = st.selectbox(
        "Select group", groups, format_func=lambda g: g.name,
    )

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    matches = crud.get_matches_by_group(session, selected_group.id)
    standings = compute_group_standings(matches)

    # Build a participant_id → member name lookup
    participants = crud.get_participants_by_tournament(session, tournament_id)
    participant_member: dict[uuid.UUID, Member] = {}
    for p in participants:
        member = crud.get_by_id(session, Member, p.member_id)
        if member:
            participant_member[p.id] = member

    def _name(pid: uuid.UUID) -> str:
        m = participant_member.get(pid)
        return f"{m.first_name} {m.last_name}" if m else "?"

    if standings:
        st.markdown("#### Standings")
        rows = []
        for i, s in enumerate(standings, 1):
            rows.append({
                "#": i,
                "Name": _name(s["participant_id"]),
                "W": s["wins"],
                "D": s["draws"],
                "L": s["losses"],
                "Pts": s["points"],
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # Matches
    # ------------------------------------------------------------------

    st.markdown("#### Matches")

    for match in matches:
        name_a = _name(match.participant_a_id)
        name_b = _name(match.participant_b_id)
        mid = str(match.id)

        with st.container(border=True):
            # Header row
            if match.completed:
                winner_name = _name(match.winner_id) if match.winner_id else "Draw"
                st.markdown(f"**{name_a}** vs **{name_b}** — *Completed* (Winner: {winner_name})")
            else:
                st.markdown(f"**{name_a}** vs **{name_b}**")

            # Score display
            col_a, col_mid, col_b = st.columns([2, 1, 2])

            with col_a:
                st.caption(name_a)
                st.write(f"Ippon: **{match.score_a_ippon}** / Waza-ari: **{match.score_a_wazari}** / Yuko: **{match.score_a_yuko}**")

            with col_mid:
                st.markdown("<div style='text-align:center; padding-top:1.5rem;'>vs</div>", unsafe_allow_html=True)

            with col_b:
                st.caption(name_b)
                st.write(f"Ippon: **{match.score_b_ippon}** / Waza-ari: **{match.score_b_wazari}** / Yuko: **{match.score_b_yuko}**")

            # Action buttons (only for active matches)
            if not match.completed:
                st.divider()
                btn_a, btn_b = st.columns(2)

                with btn_a:
                    st.caption(f"Score for {name_a}")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Ippon", key=f"ia_{mid}"):
                        match.score_a_ippon += 1
                        _auto_complete(session, match)
                    if c2.button("Waza-ari", key=f"wa_{mid}"):
                        match.score_a_wazari += 1
                        _auto_complete(session, match)
                    if c3.button("Yuko", key=f"ya_{mid}"):
                        match.score_a_yuko += 1
                        _save_match(session, match)

                with btn_b:
                    st.caption(f"Score for {name_b}")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("Ippon", key=f"ib_{mid}"):
                        match.score_b_ippon += 1
                        _auto_complete(session, match)
                    if c2.button("Waza-ari", key=f"wb_{mid}"):
                        match.score_b_wazari += 1
                        _auto_complete(session, match)
                    if c3.button("Yuko", key=f"yb_{mid}"):
                        match.score_b_yuko += 1
                        _save_match(session, match)

                # End match manually (decide by points)
                e1, e2 = st.columns(2)
                if e1.button("End match", key=f"end_{mid}"):
                    match.winner_id = determine_match_winner(match)
                    match.completed = True
                    _save_match(session, match)
                if e2.button("Reset scores", key=f"reset_{mid}"):
                    match.score_a_ippon = match.score_a_wazari = match.score_a_yuko = 0
                    match.score_b_ippon = match.score_b_wazari = match.score_b_yuko = 0
                    match.winner_id = None
                    match.completed = False
                    _save_match(session, match)

finally:
    session.close()
