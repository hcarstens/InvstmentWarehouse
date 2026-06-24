"""Phase 1 dashboard data — entity graph, securities, schema status."""

from pydantic import BaseModel

from warehouse.data.entity_graph_store import load_entity_graph
from warehouse.data.security_master import Security
from warehouse.infra.db.base import session_scope
from warehouse.infra.db.bootstrap import bootstrap_database
from warehouse.infra.db.schema_status import SchemaStatus, build_schema_status
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID
from warehouse.models.entities import EntityGraph


class Phase1DashboardData(BaseModel):
    household_id: str
    entity_graph: EntityGraph
    securities: list[Security]
    schema_status: SchemaStatus
    security_query: str | None = None
    error: str | None = None


def load_phase1_dashboard(security_query: str | None = None) -> Phase1DashboardData:
    try:
        bootstrap_database(seed=True)
        with session_scope() as session:
            from warehouse.data.security_master_store import list_securities

            graph = load_entity_graph(session, household_id=DEMO_HOUSEHOLD_ID)
            securities = list_securities(session, query=security_query)
        schema = build_schema_status()
        return Phase1DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            entity_graph=graph,
            securities=securities,
            schema_status=schema,
            security_query=security_query or None,
        )
    except Exception as err:
        schema = build_schema_status()
        return Phase1DashboardData(
            household_id=DEMO_HOUSEHOLD_ID,
            entity_graph=EntityGraph(),
            securities=[],
            schema_status=schema,
            security_query=security_query or None,
            error=str(err),
        )
