from collections.abc import Generator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from sms_demo.config import get_settings
from sms_demo.models import Base

_engine = None
_SessionLocal = None


def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


def dispose_engine() -> None:
    """Drop pooled connections (required after Celery worker fork with SQLite)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


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


def _sqlite_column_names(conn, table: str) -> set[str]:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {row[1] for row in rows}


def _migrate_sqlite(conn) -> None:
    """Add columns introduced after initial demo schema (no Alembic)."""
    intake_cols = _sqlite_column_names(conn, "intakes")
    if "pipeline_status" not in intake_cols:
        conn.execute(text("ALTER TABLE intakes ADD COLUMN pipeline_status VARCHAR(16)"))
    if "processing_completed_at" not in intake_cols:
        conn.execute(
            text("ALTER TABLE intakes ADD COLUMN processing_completed_at DATETIME")
        )
    if "processing_duration_ms" not in intake_cols:
        conn.execute(text("ALTER TABLE intakes ADD COLUMN processing_duration_ms FLOAT"))

    extraction_cols = _sqlite_column_names(conn, "extractions")
    if "llm_duration_ms" not in extraction_cols:
        conn.execute(text("ALTER TABLE extractions ADD COLUMN llm_duration_ms FLOAT"))

    # Backfill: finished intakes → complete; pending non-empty → queued
    conn.execute(
        text(
            """
            UPDATE intakes
            SET pipeline_status = 'complete'
            WHERE id IN (SELECT intake_id FROM routing_decisions)
              AND coalesce(pipeline_status, 'queued') != 'complete'
            """
        )
    )
    conn.execute(
        text(
            """
            UPDATE intakes
            SET pipeline_status = 'queued'
            WHERE pipeline_status IS NULL
              AND trim(coalesce(raw_body, '')) != ''
              AND id NOT IN (SELECT intake_id FROM routing_decisions)
            """
        )
    )


def init_database() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            if inspect(conn).has_table("intakes"):
                _migrate_sqlite(conn)
