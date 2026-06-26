"""Phase 1 — schema, entity graph, security master, dashboard data."""

from warehouse.config import get_settings
from warehouse.dashboard.phase1_data import load_phase1_dashboard
from warehouse.data.entity_graph_store import load_entity_graph
from warehouse.data.security_master_store import list_securities
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.migrate import current_revision, upgrade_head
from warehouse.infra.db.schema_status import HEAD_REVISION, build_schema_status
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


def test_migration_at_head() -> None:
    get_settings.cache_clear()
    revision = upgrade_head()
    assert revision == HEAD_REVISION
    assert current_revision() == HEAD_REVISION


def test_schema_status_current() -> None:
    status = build_schema_status()
    assert status.is_current
    assert status.current_revision == HEAD_REVISION
    table_names = {t.name for t in status.tables}
    assert "entities" in table_names
    assert "securities" in table_names
    assert "lots" in table_names
    assert status.tables[0].row_count >= 0


def test_demo_entity_graph_includes_custodian() -> None:
    with session_scope() as session:
        graph = load_entity_graph(session, household_id=DEMO_HOUSEHOLD_ID)
    entity_types = {e.entity_type.value for e in graph.entities}
    assert "household" in entity_types
    assert "account" in entity_types
    assert "custodian" in entity_types
    assert len(graph.relationships) >= 5


def test_security_master_search() -> None:
    with session_scope() as session:
        all_secs = list_securities(session)
        vti = list_securities(session, query="VTI")
    assert len(all_secs) == 3
    assert len(vti) == 1
    assert vti[0].ticker == "VTI"


def test_phase1_dashboard_loads() -> None:
    data = load_phase1_dashboard()
    assert data.error is None
    assert len(data.entity_graph.entities) >= 6
    assert len(data.securities) == 3
    assert data.schema_status.is_current


def test_workflow_definitions_seeded() -> None:
    status = build_schema_status()
    workflows = next(t for t in status.tables if t.name ==
                     "workflow_definitions")
    assert workflows.row_count == 6
