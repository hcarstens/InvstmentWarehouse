"""Phase 1 — schema, entity graph, security master, dashboard data."""

import pytest

from warehouse.config import get_settings
from warehouse.dashboard.phase1_data import load_phase1_dashboard
from warehouse.data.beneficiary_graph import (
    BeneficiaryGraphError,
    assert_beneficiary_edges_resolve,
    beneficiaries_of,
    beneficiary_entities,
    beneficiary_of_map,
)
from warehouse.data.entity_graph_store import load_entity_graph
from warehouse.data.security_master_store import list_securities
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.migrate import current_revision, upgrade_head
from warehouse.infra.db.schema_status import HEAD_REVISION, build_schema_status
from warehouse.infra.db.seed import (
    BENEFICIARY_ALEX_ID,
    BENEFICIARY_MORGAN_ID,
    DEMO_HOUSEHOLD_ID,
)
from warehouse.models.entities import RelationshipType
from warehouse.workflows.catalog import WORKFLOW_CATALOG

_DEMO_TICKERS = frozenset({"VTI", "BND", "AAPL"})

# Independent graph oracle (ST2) — designation map, not copied from loader.
_DEMO_BENEFICIARY_ORACLE: dict[str, str] = {
    BENEFICIARY_ALEX_ID: "acct_ira",
    BENEFICIARY_MORGAN_ID: "trust_smith_rev",
}


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
    assert "beneficiary" in entity_types
    assert len(graph.relationships) >= 5


def test_beneficiary_edges_match_graph_oracle() -> None:
    """qa8 — beneficiary_of designations match independent topology oracle."""
    with session_scope() as session:
        graph = load_entity_graph(session, household_id=DEMO_HOUSEHOLD_ID)
    assert beneficiary_of_map(graph) == _DEMO_BENEFICIARY_ORACLE
    assert_beneficiary_edges_resolve(graph)


def test_beneficiaries_of_ira_and_trust() -> None:
    """qa8/ST6 — per-target beneficiary lookup matches hand oracle."""
    with session_scope() as session:
        graph = load_entity_graph(session, household_id=DEMO_HOUSEHOLD_ID)
    assert beneficiaries_of(graph, "acct_ira") == [BENEFICIARY_ALEX_ID]
    assert beneficiaries_of(graph, "trust_smith_rev") == [
        BENEFICIARY_MORGAN_ID
    ]
    assert beneficiaries_of(graph, "acct_taxable") == []


def test_beneficiary_entities_household_scoped() -> None:
    """qa8 — every beneficiary node belongs to the demo household."""
    with session_scope() as session:
        graph = load_entity_graph(session, household_id=DEMO_HOUSEHOLD_ID)
    beneficiaries = beneficiary_entities(graph)
    assert {b.entity_id for b in beneficiaries} == set(
        _DEMO_BENEFICIARY_ORACLE
    )
    assert all(b.household_id == DEMO_HOUSEHOLD_ID for b in beneficiaries)


def test_beneficiary_edge_validation_rejects_bad_source_type() -> None:
    """qa8 — beneficiary_of from a non-beneficiary entity must not pass."""
    with session_scope() as session:
        graph = load_entity_graph(session, household_id=DEMO_HOUSEHOLD_ID)
    bad = graph.model_copy(
        update={
            "relationships": [
                *graph.relationships,
                graph.relationships[0].model_copy(
                    update={
                        "relationship_type": RelationshipType.BENEFICIARY_OF,
                    }
                ),
            ]
        }
    )
    with pytest.raises(BeneficiaryGraphError, match="expected beneficiary"):
        assert_beneficiary_edges_resolve(bad)


def test_security_master_search() -> None:
    with session_scope() as session:
        all_secs = list_securities(session)
        vti = list_securities(session, query="VTI")
    tickers = {s.ticker for s in all_secs if s.ticker}
    assert _DEMO_TICKERS.issubset(tickers)
    assert len(vti) == 1
    assert vti[0].ticker == "VTI"


def test_phase1_dashboard_loads() -> None:
    data = load_phase1_dashboard()
    assert data.error is None
    assert len(data.entity_graph.entities) >= 8
    tickers = {s.ticker for s in data.securities if s.ticker}
    assert _DEMO_TICKERS.issubset(tickers)
    assert data.schema_status.is_current
    rel_types = {r.relationship_type for r in data.entity_graph.relationships}
    assert RelationshipType.BENEFICIARY_OF in rel_types


def test_workflow_definitions_seeded() -> None:
    status = build_schema_status()
    workflows = next(
        t for t in status.tables if t.name == "workflow_definitions"
    )
    assert workflows.row_count == len(WORKFLOW_CATALOG)
