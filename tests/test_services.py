from sqlmodel import Session, SQLModel

from backend.db import get_engine
from backend.services import (
    CSV_COLUMNS,
    generate_results_report,
    get_draft_participant_order,
    get_filtered_participants,
    import_participants_csv,
    list_groups_with_participants,
    save_match_result,
    set_groups,
)


def _new_session():
    engine = get_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_complete_tournament_workflow():
    csv_text = "\n".join(
        [
            ",".join(CSV_COLUMNS),
            "Doe,John,ClubA,M,U15,50",
            "Smith,Jane,ClubB,F,U15,48",
            "Doe,Jack,ClubA,M,U18,68",
        ]
    )

    with _new_session() as session:
        created = import_participants_csv(session, csv_text.encode("utf-8"))
        assert created == 3

        males = get_filtered_participants(session, sex="M")
        assert len(males) == 2
        by_name = get_filtered_participants(session, name_query="jane")
        assert len(by_name) == 1
        assert by_name[0].last_name == "Smith"

        draft_ids = get_draft_participant_order(session)
        assert len(draft_ids) == 3

        set_groups(
            session,
            [
                {"name": "Group 1", "participant_ids": [draft_ids[0], draft_ids[1]]},
                {"name": "Group 2", "participant_ids": [draft_ids[2]]},
            ],
        )
        groups = list_groups_with_participants(session)
        assert len(groups) == 2

        g1 = groups[0]["group"]
        p1 = groups[0]["participants"][0]
        p2 = groups[0]["participants"][1]
        save_match_result(
            session,
            group_id=g1.id,
            participant_a_id=p1.id,
            participant_b_id=p2.id,
            winner_id=p1.id,
            notes="Ippon",
        )
        report = generate_results_report(session)
        assert "Group: Group 1" in report
        assert "Winner:" in report
