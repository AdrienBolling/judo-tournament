from __future__ import annotations

import streamlit as st
from sqlmodel import Session, select

from backend.db import get_engine, init_db
from backend.models import Participant
from backend.services import (
    generate_results_report,
    get_draft_participant_order,
    get_filtered_participants,
    import_participants_csv,
    list_groups_with_participants,
    list_unique_values,
    save_match_result,
    set_groups,
)


st.set_page_config(page_title="Judo Tournament Manager", layout="wide")
st.title("Judo Tournament Manager")

engine = get_engine()
init_db(engine)

with Session(engine) as session:
    st.header("1) Import inscriptions CSV")
    uploaded = st.file_uploader("Upload CSV", type=["csv"])
    replace_existing = st.checkbox("Replace existing data", value=True)
    if uploaded is not None and st.button("Import participants"):
        try:
            created = import_participants_csv(session, uploaded.getvalue(), replace_existing=replace_existing)
            st.success(f"Imported {created} participants.")
        except Exception as exc:
            st.error(str(exc))

    st.header("2) Participants filters & search")
    sexes = [""] + list_unique_values(session, "sex")
    age_categories = [""] + list_unique_values(session, "age_category")
    clubs = [""] + list_unique_values(session, "club")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sex = st.selectbox("Sex", sexes)
    with c2:
        age_category = st.selectbox("Age category", age_categories)
    with c3:
        club = st.selectbox("Club", clubs)
    with c4:
        name_query = st.text_input("Search by first/last name")

    filtered = get_filtered_participants(
        session,
        sex=sex or None,
        age_category=age_category or None,
        club=club or None,
        name_query=name_query or None,
    )
    st.caption(f"{len(filtered)} participant(s)")
    st.dataframe(
        [
            {
                "id": p.id,
                "last_name": p.last_name,
                "first_name": p.first_name,
                "club": p.club,
                "sex": p.sex,
                "age_category": p.age_category,
                "weight": p.weight,
            }
            for p in filtered
        ],
        use_container_width=True,
    )

    st.header("3) Group creation")
    if st.button("Generate first draft (placeholder optimization)"):
        ordered_ids = get_draft_participant_order(session)
        st.session_state["draft_participant_ids"] = ordered_ids
        st.info("Draft generated with placeholder strategy (sorted by weight).")

    participants = list(session.exec(select(Participant).order_by(Participant.last_name, Participant.first_name)))
    participant_options = {
        f"{p.first_name} {p.last_name} ({p.club}, {p.weight}kg)": p.id for p in participants if p.id is not None
    }

    group_count = st.number_input("Number of groups", min_value=1, max_value=32, value=2, step=1)
    group_payloads = []
    cols = st.columns(int(group_count))
    for idx in range(int(group_count)):
        with cols[idx]:
            st.subheader(f"Group {idx + 1}")
            group_name = st.text_input("Name", value=f"Group {idx + 1}", key=f"group_name_{idx}")
            selected = st.multiselect(
                "Participants",
                options=list(participant_options.keys()),
                key=f"group_members_{idx}",
            )
            group_payloads.append(
                {
                    "name": group_name,
                    "participant_ids": [participant_options[s] for s in selected],
                }
            )

    if st.button("Save groups"):
        set_groups(session, group_payloads)
        st.success("Groups saved.")

    st.subheader("Current groups")
    for group_data in list_groups_with_participants(session):
        group = group_data["group"]
        st.markdown(f"**{group.name}**")
        if not group_data["participants"]:
            st.write("- Empty")
        for p in group_data["participants"]:
            st.write(f"- {p.first_name} {p.last_name} ({p.club})")

    st.header("4) Match results and report")
    group_entries = list_groups_with_participants(session)
    group_map = {f"{g['group'].name} (id={g['group'].id})": g for g in group_entries if g["group"].id is not None}
    selected_group_label = st.selectbox("Group for result input", [""] + list(group_map.keys()))
    if selected_group_label:
        selected_group = group_map[selected_group_label]
        p_map = {
            f"{p.first_name} {p.last_name}": p.id
            for p in selected_group["participants"]
            if p.id is not None
        }
        p_labels = list(p_map.keys())
        a_col, b_col, w_col = st.columns(3)
        with a_col:
            p1 = st.selectbox("Participant A", [""] + p_labels)
        with b_col:
            p2 = st.selectbox("Participant B", [""] + p_labels)
        with w_col:
            winner = st.selectbox("Winner", [""] + p_labels)
        notes = st.text_input("Notes")
        if st.button("Save result"):
            if not p1 or not p2 or not winner:
                st.error("Please select both participants and the winner.")
            elif p1 == p2:
                st.error("Participant A and B must be different.")
            else:
                save_match_result(
                    session,
                    group_id=selected_group["group"].id,
                    participant_a_id=p_map[p1],
                    participant_b_id=p_map[p2],
                    winner_id=p_map[winner],
                    notes=notes,
                )
                st.success("Result saved.")

    report_text = generate_results_report(session)
    st.text_area("Generated report", report_text, height=320)
    st.download_button(
        "Download report (.txt)",
        data=report_text.encode("utf-8"),
        file_name="results_report.txt",
        mime="text/plain",
    )
