"""Apply migrations and seed demo data."""

from warehouse.infra.db.base import session_scope
from warehouse.infra.db.migrate import upgrade_head
from warehouse.infra.db.seed import seed_demo_data


def bootstrap_database(seed: bool = True) -> str:
    """Migrate to head and optionally seed demo household. Errors bubble up."""
    revision = upgrade_head()
    if seed:
        with session_scope() as session:
            seed_demo_data(session)
    return revision
