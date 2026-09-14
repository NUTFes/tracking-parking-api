import contextlib
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextlib.contextmanager
def session_scope() -> Iterator[Session]:
    """Same open/close-in-finally shape as get_db, for code that runs
    outside a request (BackgroundTasks, the periodic sweep loop) and can't
    use get_db's FastAPI dependency form. Calls SessionLocal via this
    module's own global rather than a captured reference so tests can
    monkeypatch database.SessionLocal to the test engine and have it take
    effect here too."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
