"""Idempotent demo seed — Smith household vertical slice preview."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.infra.db.models import (
    EntityRelationshipRow,
    EntityRow,
    LotRow,
    MarketPriceRow,
    SecurityRow,
    WorkflowDefinitionRow,
)
from warehouse.models.entities import EntityType, RelationshipType
from warehouse.workflows.catalog import WORKFLOW_CATALOG

DEMO_HOUSEHOLD_ID = "hh_smith"


def seed_market_prices(session: Session) -> None:
    existing = session.scalar(select(MarketPriceRow.security_id).limit(1))
    if existing:
        return
    prices = [
        ("sec_vti", Decimal("245.50")),
        ("sec_bnd", Decimal("73.10")),
        ("sec_aapl", Decimal("195.20")),
    ]
    as_of = date(2026, 6, 24)
    session.add_all(
        [MarketPriceRow(security_id=s, price=p, as_of_date=as_of) for s, p in prices]
    )


def seed_demo_data(session: Session) -> bool:
    """Insert demo graph, securities, lots, workflows. Returns True if newly seeded."""
    existing = session.scalar(
        select(EntityRow).where(EntityRow.entity_id == DEMO_HOUSEHOLD_ID)
    )
    if existing:
        seed_market_prices(session)
        return False

    entities = [
        EntityRow(
            entity_id=DEMO_HOUSEHOLD_ID,
            entity_type=EntityType.HOUSEHOLD,
            name="Smith Family",
            household_id=DEMO_HOUSEHOLD_ID,
        ),
        EntityRow(
            entity_id="person_smith",
            entity_type=EntityType.PERSON,
            name="John Smith",
            household_id=DEMO_HOUSEHOLD_ID,
        ),
        EntityRow(
            entity_id="trust_smith_rev",
            entity_type=EntityType.TRUST,
            name="Smith Revocable Trust",
            household_id=DEMO_HOUSEHOLD_ID,
        ),
        EntityRow(
            entity_id="acct_taxable",
            entity_type=EntityType.ACCOUNT,
            name="Schwab Taxable",
            household_id=DEMO_HOUSEHOLD_ID,
        ),
        EntityRow(
            entity_id="acct_ira",
            entity_type=EntityType.ACCOUNT,
            name="Schwab IRA",
            household_id=DEMO_HOUSEHOLD_ID,
        ),
        EntityRow(
            entity_id="custodian_schwab",
            entity_type=EntityType.CUSTODIAN,
            name="Charles Schwab",
            household_id=None,
        ),
    ]
    relationships = [
        EntityRelationshipRow(
            source_id=DEMO_HOUSEHOLD_ID,
            target_id="person_smith",
            relationship_type=RelationshipType.AGGREGATES,
        ),
        EntityRelationshipRow(
            source_id=DEMO_HOUSEHOLD_ID,
            target_id="trust_smith_rev",
            relationship_type=RelationshipType.AGGREGATES,
        ),
        EntityRelationshipRow(
            source_id=DEMO_HOUSEHOLD_ID,
            target_id="acct_taxable",
            relationship_type=RelationshipType.AGGREGATES,
        ),
        EntityRelationshipRow(
            source_id=DEMO_HOUSEHOLD_ID,
            target_id="acct_ira",
            relationship_type=RelationshipType.AGGREGATES,
        ),
        EntityRelationshipRow(
            source_id="person_smith",
            target_id="trust_smith_rev",
            relationship_type=RelationshipType.OWNS,
        ),
        EntityRelationshipRow(
            source_id="trust_smith_rev",
            target_id="acct_taxable",
            relationship_type=RelationshipType.HOLDS,
        ),
        EntityRelationshipRow(
            source_id="person_smith",
            target_id="acct_ira",
            relationship_type=RelationshipType.OWNS,
        ),
        EntityRelationshipRow(
            source_id="acct_taxable",
            target_id="custodian_schwab",
            relationship_type=RelationshipType.CUSTODIED_AT,
        ),
        EntityRelationshipRow(
            source_id="acct_ira",
            target_id="custodian_schwab",
            relationship_type=RelationshipType.CUSTODIED_AT,
        ),
    ]
    securities = [
        SecurityRow(
            security_id="sec_vti",
            ticker="VTI",
            cusip="922908769",
            name="Vanguard Total Stock Market ETF",
            asset_class=AssetClass.ETF,
            tax_character=TaxCharacter.LTCG,
            liquidity_tier=1,
            wash_sale_substitute_group="us_equity_broad",
        ),
        SecurityRow(
            security_id="sec_bnd",
            ticker="BND",
            cusip="921937835",
            name="Vanguard Total Bond Market ETF",
            asset_class=AssetClass.ETF,
            tax_character=TaxCharacter.LTCG,
            liquidity_tier=1,
            wash_sale_substitute_group="us_bond_broad",
        ),
        SecurityRow(
            security_id="sec_aapl",
            ticker="AAPL",
            cusip="037833100",
            name="Apple Inc",
            asset_class=AssetClass.EQUITY,
            tax_character=TaxCharacter.LTCG,
            liquidity_tier=1,
            wash_sale_substitute_group="us_equity_tech",
        ),
    ]
    lots = [
        LotRow(
            lot_id="lot_vti_1",
            account_id="acct_taxable",
            security_id="sec_vti",
            quantity=Decimal("500"),
            cost_basis_per_share=Decimal("210.00"),
            acquisition_date=date(2023, 4, 10),
        ),
        LotRow(
            lot_id="lot_aapl_1",
            account_id="acct_taxable",
            security_id="sec_aapl",
            quantity=Decimal("100"),
            cost_basis_per_share=Decimal("145.50"),
            acquisition_date=date(2024, 1, 15),
            is_restricted=True,
        ),
        LotRow(
            lot_id="lot_bnd_1",
            account_id="acct_ira",
            security_id="sec_bnd",
            quantity=Decimal("300"),
            cost_basis_per_share=Decimal("72.25"),
            acquisition_date=date(2022, 8, 1),
        ),
    ]
    workflows = [
        WorkflowDefinitionRow(
            name=w.name,
            owner=w.owner,
            inputs=json.dumps(w.inputs),
            outputs=json.dumps(w.outputs),
            sla_hours=w.sla_hours,
        )
        for w in WORKFLOW_CATALOG
    ]

    session.add_all(entities)
    session.add_all(relationships)
    session.add_all(securities)
    session.add_all(lots)
    session.add_all(workflows)
    seed_market_prices(session)
    return True
