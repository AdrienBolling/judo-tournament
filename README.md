# judo-tournament
A simple Python-based Streamlit Web App to help manage my small judo tournaments by generating groups from the inscription tables and generating results reports.

## Run locally

```bash
pip install -e .
streamlit run app.py
```

The app uses SQLite through SQLModel/SQLAlchemy and stores data in `tournament.db`.

Expected CSV columns:

`last_name, first_name, club, sex, age_category, weight`
