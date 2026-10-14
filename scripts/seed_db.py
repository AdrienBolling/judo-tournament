"""Populate the database with realistic fake data for development/demo."""

from datetime import date

from backend.auth import generate_referee_token, hash_password
from backend.database import crud
from backend.database.database import get_session, init_db
from backend.database.models import (
    AdminUser,
    Club,
    Coach,
    Member,
    RefereeToken,
    Tournament,
)
from backend.solver.ga_solver import GAConfig
from backend.tournament import register_members_for_tournament, setup_tournament_groups

init_db()
session = get_session()

# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

admin = crud.create(
    session,
    AdminUser(username="admin", password_hash=hash_password("admin")),
)
print(f"Admin created  -> username: admin / password: admin")

# ---------------------------------------------------------------------------
# Clubs
# ---------------------------------------------------------------------------

club_lyon = crud.create(session, Club(name="Judo Club Lyon", location="Lyon"))
club_marseille = crud.create(session, Club(name="Olympique Marseille Judo", location="Marseille"))
club_paris = crud.create(session, Club(name="Paris Judo Academy", location="Paris"))
club_bordeaux = crud.create(session, Club(name="Bordeaux Judo", location="Bordeaux"))

print(f"Created 4 clubs")

# ---------------------------------------------------------------------------
# Coaches (password = club city lowercase, e.g. "lyon")
# ---------------------------------------------------------------------------

coaches_data = [
    ("Yuki", "Tanaka", club_lyon, "yuki.tanaka@lyon-judo.fr", "0612345678", "lyon"),
    ("Marc", "Dubois", club_lyon, "marc.dubois@lyon-judo.fr", "0612345679", "lyon"),
    ("Karim", "Benzema", club_marseille, "karim@om-judo.fr", "0698765432", "marseille"),
    ("Sophie", "Laurent", club_paris, "sophie@paris-judo.fr", "0611223344", "paris"),
    ("Antoine", "Griezmann", club_bordeaux, "antoine@bordeaux-judo.fr", "0655667788", "bordeaux"),
]

for fn, ln, club, email, phone, pwd in coaches_data:
    crud.create(
        session,
        Coach(
            first_name=fn, last_name=ln, club_id=club.id,
            email=email, phone_number=phone,
            password_hash=hash_password(pwd),
        ),
    )

print(f"Created {len(coaches_data)} coaches")

# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------

members_spec = [
    # Lyon (10 members)
    ("Jean", "Dupont", date(1998, 3, 15), 73.0, "M", club_lyon),
    ("Marie", "Bernard", date(2005, 7, 22), 57.0, "F", club_lyon),
    ("Luc", "Durand", date(2000, 1, 10), 81.0, "M", club_lyon),
    ("Claire", "Moreau", date(2001, 9, 20), 52.0, "F", club_lyon),
    ("Hugo", "Garcia", date(1997, 4, 8), 90.0, "M", club_lyon),
    ("Emma", "Lefevre", date(2004, 11, 30), 48.0, "F", club_lyon),
    ("Thomas", "Roux", date(1999, 6, 3), 66.0, "M", club_lyon),
    ("Lea", "Fournier", date(2003, 2, 14), 63.0, "F", club_lyon),
    ("Nathan", "Girard", date(2002, 8, 25), 78.0, "M", club_lyon),
    ("Camille", "Andre", date(2006, 12, 5), 55.0, "F", club_lyon),
    # Marseille (8 members)
    ("Pierre", "Martin", date(2003, 5, 5), 66.0, "M", club_marseille),
    ("Sophie", "Petit", date(1999, 12, 1), 60.0, "F", club_marseille),
    ("Antoine", "Robert", date(1998, 10, 18), 73.0, "M", club_marseille),
    ("Julie", "Richard", date(2001, 3, 27), 52.0, "F", club_marseille),
    ("Maxime", "Dumont", date(2000, 7, 14), 81.0, "M", club_marseille),
    ("Alice", "Simon", date(2005, 1, 9), 57.0, "F", club_marseille),
    ("Romain", "Michel", date(1997, 11, 22), 90.0, "M", club_marseille),
    ("Ines", "Leroy", date(2004, 4, 16), 48.0, "F", club_marseille),
    # Paris (8 members)
    ("Lucas", "Lefebvre", date(2002, 9, 11), 78.0, "M", club_paris),
    ("Manon", "Morel", date(2000, 6, 30), 63.0, "F", club_paris),
    ("Theo", "Lambert", date(1999, 2, 8), 73.0, "M", club_paris),
    ("Chloe", "Bonnet", date(2003, 8, 19), 55.0, "F", club_paris),
    ("Enzo", "Francois", date(1998, 12, 4), 66.0, "M", club_paris),
    ("Sarah", "Martinez", date(2001, 5, 23), 60.0, "F", club_paris),
    ("Mathis", "Legrand", date(2005, 10, 7), 81.0, "M", club_paris),
    ("Eva", "Garnier", date(2004, 3, 12), 52.0, "F", club_paris),
    # Bordeaux (6 members)
    ("Louis", "Faure", date(2000, 11, 15), 90.0, "M", club_bordeaux),
    ("Jade", "Mercier", date(2002, 7, 28), 48.0, "F", club_bordeaux),
    ("Gabriel", "Dupuis", date(1999, 4, 2), 78.0, "M", club_bordeaux),
    ("Lina", "Fontaine", date(2003, 1, 20), 57.0, "F", club_bordeaux),
    ("Adam", "Chevalier", date(2001, 9, 6), 66.0, "M", club_bordeaux),
    ("Zoe", "Renaud", date(2005, 6, 17), 55.0, "F", club_bordeaux),
]

all_members = []
for fn, ln, dob, w, g, club in members_spec:
    m = crud.create(
        session,
        Member(
            first_name=fn, last_name=ln, date_of_birth=dob,
            weight=w, gender=g, club_id=club.id,
        ),
    )
    all_members.append((m, club))

print(f"Created {len(all_members)} members")

# ---------------------------------------------------------------------------
# Tournament 1 — past (with groups + scored matches)
# ---------------------------------------------------------------------------

t1 = crud.create(
    session,
    Tournament(
        name="Open de Lyon 2025",
        date=date(2025, 11, 15),
        location="Palais des Sports de Lyon",
        hosting_club_id=club_lyon.id,
    ),
)

# Register all members
register_members_for_tournament(session, t1.id, [m.id for m, _ in all_members])
print(f"Tournament '{t1.name}': {len(all_members)} participants registered")

# Generate groups
config = GAConfig(
    max_group_size=5, max_additional_groups=2,
    small_swaps=3, big_swaps=1,
    population_size=50, generations=80, mutation_rate=0.4,
    scores_weights={"gender": 1.0, "weight": 3.0, "club": 1.0, "group_size": 0.5, "nb_groups": 0.5},
)
groups = setup_tournament_groups(session, t1.id, config)
print(f"  Generated {len(groups)} groups")

# Score some matches in each group to simulate a past tournament
import random
random.seed(42)

for g in groups:
    matches = crud.get_matches_by_group(session, g.id)
    for match in matches:
        # Randomly score the match
        outcome = random.choice(["ippon_a", "ippon_b", "wazari", "points"])
        if outcome == "ippon_a":
            match.score_a_ippon = 1
            match.winner_id = match.participant_a_id
        elif outcome == "ippon_b":
            match.score_b_ippon = 1
            match.winner_id = match.participant_b_id
        elif outcome == "wazari":
            match.score_a_wazari = random.randint(0, 2)
            match.score_b_wazari = random.randint(0, 1)
            match.score_a_yuko = random.randint(0, 3)
            match.score_b_yuko = random.randint(0, 3)
            if match.score_a_wazari >= 2:
                match.winner_id = match.participant_a_id
            elif match.score_b_wazari >= 2:
                match.winner_id = match.participant_b_id
            else:
                total_a = match.score_a_wazari * 10 + match.score_a_yuko
                total_b = match.score_b_wazari * 10 + match.score_b_yuko
                if total_a > total_b:
                    match.winner_id = match.participant_a_id
                elif total_b > total_a:
                    match.winner_id = match.participant_b_id
        else:
            match.score_a_yuko = random.randint(1, 4)
            match.score_b_yuko = random.randint(0, 3)
            if match.score_a_yuko > match.score_b_yuko:
                match.winner_id = match.participant_a_id
            elif match.score_b_yuko > match.score_a_yuko:
                match.winner_id = match.participant_b_id
        match.completed = True
        session.add(match)

    session.commit()

scored = sum(len(crud.get_matches_by_group(session, g.id)) for g in groups)
print(f"  Scored {scored} matches")

# Referee token for tournament 1
tk1 = crud.create(
    session,
    RefereeToken(token=generate_referee_token(), label="Table 1", tournament_id=t1.id),
)
print(f"  Referee token (Table 1): {tk1.token}")

# ---------------------------------------------------------------------------
# Tournament 2 — upcoming (participants registered, no groups yet)
# ---------------------------------------------------------------------------

t2 = crud.create(
    session,
    Tournament(
        name="Tournoi de Printemps 2026",
        date=date(2026, 4, 25),
        location="Gymnase Municipal de Marseille",
        hosting_club_id=club_marseille.id,
    ),
)

# Register a subset of members
t2_members = [m for m, club in all_members if club in (club_lyon, club_marseille, club_paris)]
register_members_for_tournament(session, t2.id, [m.id for m in t2_members])

tk2 = crud.create(
    session,
    RefereeToken(token=generate_referee_token(), label="Table A", tournament_id=t2.id),
)
tk3 = crud.create(
    session,
    RefereeToken(token=generate_referee_token(), label="Table B", tournament_id=t2.id),
)

print(f"Tournament '{t2.name}': {len(t2_members)} participants, no groups yet")
print(f"  Referee tokens: Table A = {tk2.token}  /  Table B = {tk3.token}")

# ---------------------------------------------------------------------------
# Summary (capture values before closing session)
# ---------------------------------------------------------------------------

t1_name, t2_name = t1.name, t2.name
tk1_token, tk2_token, tk3_token = tk1.token, tk2.token, tk3.token

session.close()

print("\n" + "=" * 60)
print("DATABASE SEEDED SUCCESSFULLY")
print("=" * 60)
print()
print("Logins:")
print("  Admin       -> username: admin       / password: admin")
print("  Coach Lyon  -> email: yuki.tanaka@lyon-judo.fr / password: lyon")
print("  Coach Mars. -> email: karim@om-judo.fr         / password: marseille")
print("  Coach Paris -> email: sophie@paris-judo.fr      / password: paris")
print("  Coach Bord. -> email: antoine@bordeaux-judo.fr  / password: bordeaux")
print()
print("Referee tokens:")
print(f"  {t1_name} (Table 1): {tk1_token}")
print(f"  {t2_name} (Table A): {tk2_token}")
print(f"  {t2_name} (Table B): {tk3_token}")
print()
print("Run the app with:  uv run streamlit run src/app/main.py")
