from sqlmodel import SQLModel, create_engine


def get_engine(db_url: str = "sqlite:///tournament.db"):
    return create_engine(db_url, connect_args={"check_same_thread": False})


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)
