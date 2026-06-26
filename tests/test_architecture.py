"""Architecture and domain model smoke tests."""

from decimal import Decimal

from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.models.entities import (
    Entity,
    EntityGraph,
    EntityType,
    Relationship,
    RelationshipType,
)
from warehouse.workflows.catalog import WORKFLOW_CATALOG


def test_workflow_catalog_has_six_core_workflows() -> None:
    names = {w.name for w in WORKFLOW_CATALOG}
    assert names == {
        "onboarding",
        "daily_refresh",
        "policy_monitoring",
        "research_scenario",
        "rebalance_tax_overlay",
        "alternatives",
    }


def test_entity_graph_models() -> None:
    graph = EntityGraph(
        entities=[
            Entity(
                entity_id="hh_1",
                entity_type=EntityType.HOUSEHOLD,
                name="Smith Family",
            ),
            Entity(
                entity_id="acct_1",
                entity_type=EntityType.ACCOUNT,
                name="Taxable",
                household_id="hh_1",
            ),
        ],
        relationships=[
            Relationship(
                source_id="hh_1",
                target_id="acct_1",
                relationship_type=RelationshipType.AGGREGATES,
            )
        ],
    )
    assert len(graph.entities) == 2
    assert (
        graph.relationships[0].relationship_type == RelationshipType.AGGREGATES
    )


def test_security_master_tax_attributes(sample_security) -> None:
    assert sample_security.asset_class == AssetClass.ETF
    assert sample_security.tax_character == TaxCharacter.LTCG
    assert sample_security.wash_sale_substitute_group == "us_equity_broad"


def test_lot_ledger_holding_period(sample_lot) -> None:
    assert sample_lot.quantity == Decimal("100")
    assert sample_lot.cost_basis_per_share == Decimal("220.50")
