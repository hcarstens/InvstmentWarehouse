"""Database engine factory."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from warehouse.config import Settings, get_settings


def create_db_engine(settings: Settings | None = None) -> Engine:
    cfg = settings or get_settings()
    return create_engine(cfg.database_url, pool_pre_ping=True)
