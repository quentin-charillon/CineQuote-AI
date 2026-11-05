from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def create_database_engine(database_url: str) -> Engine:
    is_sqlite = database_url.startswith("sqlite")
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if is_sqlite else {},
        pool_pre_ping=not is_sqlite,
    )
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection: object, _connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine = create_database_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
