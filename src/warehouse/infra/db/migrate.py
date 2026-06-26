"""Alembic migration helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Engine

from alembic import command
from warehouse.config import get_settings, repo_root
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.engine import create_db_engine
from warehouse.infra.db.models import SchemaMigrationMetaRow


def alembic_config() -> Config:
    ini_path = repo_root() / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(repo_root() / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def current_revision(engine: Engine | None = None) -> str | None:
    eng = engine or create_db_engine()
    with eng.connect() as conn:
        inspector = inspect(conn)
        if "alembic_version" not in inspector.get_table_names():
            return None
        row = conn.execute(
            text("SELECT version_num FROM alembic_version")
        ).fetchone()
        return row[0] if row else None


def record_migration_meta(revision: str) -> None:
    with session_scope() as session:
        exists = session.scalar(
            select(SchemaMigrationMetaRow.id).where(
                SchemaMigrationMetaRow.revision == revision
            )
        )
        if exists:
            return
        session.add(
            SchemaMigrationMetaRow(
                revision=revision, applied_at=datetime.now(UTC)
            )
        )


def head_revision() -> str:
    script = ScriptDirectory.from_config(alembic_config())
    head = script.get_current_head()
    if head is None:
        raise RuntimeError("No alembic head revision configured")
    return head


def upgrade_head() -> str:
    """Apply all pending migrations. Returns current revision id."""
    cfg = alembic_config()
    command.upgrade(cfg, "head")
    revision = current_revision()
    if revision is None:
        raise RuntimeError("Migration finished but alembic_version is empty")
    record_migration_meta(revision)
    return revision


def ensure_migrated() -> str:
    """Upgrade to head if needed."""
    head = head_revision()
    revision = current_revision()
    if revision != head:
        return upgrade_head()
    return revision or head
