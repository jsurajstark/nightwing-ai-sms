from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from sms_demo.config import get_settings

_engine = None
_SessionLocal = None


def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        connect_args: dict = {}
        if settings.database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            connect_args["timeout"] = 30.0
        _engine = create_engine(settings.database_url, connect_args=connect_args)
        if settings.database_url.startswith("sqlite"):
            event.listen(_engine, "connect", _set_sqlite_pragma)
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def session_scope() -> Generator[Session, None, None]:
    get_engine()
    db = _SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Generator[Session, None, None]:
    get_engine()
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
