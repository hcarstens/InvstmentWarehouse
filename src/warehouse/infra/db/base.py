"""SQLAlchemy declarative base and session factory."""

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from warehouse.infra.db.engine import create_db_engine


class Base(DeclarativeBase):
    pass


def get_session_factory() -> sessionmaker[Session]:
    engine = create_db_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
