"""Idempotent demo seed — Smith household vertical slice preview."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse.data.security_master import AssetClass, TaxCharacter
from warehouse.decision.ips import AllocationTarget, InvestmentPolicyStatement
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.ips.store import save_ips
from warehouse.infra.db.models import (
    AlternativeEventRow,
    AlternativeHoldingRow,
    EntityRelationshipRow,
    EntityRow,
    IpsPolicyRow,
    LotRow,
    MarketPriceRow,
    RealizedGainEventRow,
    SecurityRow,
    WorkflowDefinitionRow,
)
from warehouse.models.entities import EntityType, RelationshipType
from warehouse.workflows.catalog import WORKFLOW_CATALOG

DEMO_HOUSEHOLD_ID = "hh_smith"


def _demo_ips_statement() -> InvestmentPolicyStatement:
    return InvestmentPolicyStatement(
        ips_id="ips_smith_v1",
        household_id=DEMO_HOUSEHOLD_ID,
        version=1,
        effective_date="2026-01-01",
        allocation_targets=[
            AllocationTarget(
                asset_class=IpsSleeve.EQUITY,
                min_weight=Decimal("0.70"),
                max_weight=Decimal("0.80"),
                target_weight=Decimal("0.75"),
            ),
            AllocationTarget(
                asset_class=IpsSleeve.FIXED_INCOME,
                min_weight=Decimal("0.20"),
                max_weight=Decimal("0.30"),
                target_weight=Decimal("0.25"),
            ),
        ],
        restricted_securities=[],
        concentration_limit_pct=Decimal("0.25"),
        liquidity_tier_min_pct=Decimal("0.50"),
        turnover_budget_pct=Decimal("0.15"),
    )


def seed_ips_policy(session: Session) -> None:
    existing = session.scalar(
        select(IpsPolicyRow)
        .where(IpsPolicyRow.household_id == DEMO_HOUSEHOLD_ID)
        .limit(1)
    )
    demo = _demo_ips_statement()
    if existing:
        from warehouse.decision.ips.store import row_to_ips

        current = row_to_ips(existing)
        if current.turnover_budget_pct is not None:
            return
        session.delete(existing)
    save_ips(
        session,
        demo,
    )


def seed_demo_lots(session: Session) -> None:
    """Add demo lots introduced after initial seed (idempotent)."""
    if session.get(LotRow, "lot_vti_2"):
        return
    session.add(
        LotRow(
            lot_id="lot_vti_2",
            account_id="acct_taxable",
            security_id="sec_vti",
            quantity=Decimal("50"),
            cost_basis_per_share=Decimal("255.00"),
            acquisition_date=date(2025, 3, 1),
        )
    )


def seed_phase4_extensions(session: Session) -> None:
    """Fidelity custodian, alt holding, and lots (idempotent upgrades)."""
    if not session.scalar(
        select(EntityRow.entity_id)
        .where(EntityRow.entity_id == "custodian_fidelity")
        .limit(1)
    ):
        session.add(
            EntityRow(
                entity_id="custodian_fidelity",
                entity_type=EntityType.CUSTODIAN,
                name="Fidelity Investments",
                household_id=None,
            )
        )
    if not session.scalar(
        select(EntityRow.entity_id)
        .where(EntityRow.entity_id == "acct_fidelity")
        .limit(1)
    ):
        session.add(
            EntityRow(
                entity_id="acct_fidelity",
                entity_type=EntityType.ACCOUNT,
                name="Fidelity Taxable",
                household_id=DEMO_HOUSEHOLD_ID,
            )
        )
        session.add(
            EntityRelationshipRow(
                source_id=DEMO_HOUSEHOLD_ID,
                target_id="acct_fidelity",
                relationship_type=RelationshipType.AGGREGATES,
            )
        )
        session.add(
            EntityRelationshipRow(
                source_id="trust_smith_rev",
                target_id="acct_fidelity",
                relationship_type=RelationshipType.HOLDS,
            )
        )
        session.add(
            EntityRelationshipRow(
                source_id="acct_fidelity",
                target_id="custodian_fidelity",
                relationship_type=RelationshipType.CUSTODIED_AT,
            )
        )
    if not session.scalar(
        select(LotRow.lot_id)
        .where(LotRow.lot_id == "lot_fidelity_vti")
        .limit(1)
    ):
        session.add(
            LotRow(
                lot_id="lot_fidelity_vti",
                account_id="acct_fidelity",
                security_id="sec_vti",
                quantity=Decimal("200"),
                cost_basis_per_share=Decimal("230.00"),
                acquisition_date=date(2024, 6, 1),
            )
        )
    if not session.scalar(
        select(LotRow.lot_id)
        .where(LotRow.lot_id == "lot_fidelity_bnd")
        .limit(1)
    ):
        session.add(
            LotRow(
                lot_id="lot_fidelity_bnd",
                account_id="acct_fidelity",
                security_id="sec_bnd",
                quantity=Decimal("150"),
                cost_basis_per_share=Decimal("74.00"),
                acquisition_date=date(2023, 11, 15),
            )
        )
    if not session.scalar(
        select(AlternativeHoldingRow.holding_id)
        .where(AlternativeHoldingRow.holding_id == "alt_pe_smith")
        .limit(1)
    ):
        session.add(
            AlternativeHoldingRow(
                holding_id="alt_pe_smith",
                household_id=DEMO_HOUSEHOLD_ID,
                entity_id="trust_smith_rev",
                name="Smith Growth PE Fund II",
                asset_type="private_equity",
                committed_capital=Decimal("500000.00"),
                called_capital=Decimal("350000.00"),
                current_nav=Decimal("410000.00"),
                last_mark_date=date(2026, 3, 31),
            )
        )
        session.add(
            AlternativeEventRow(
                event_id="alt_evt_call_1",
                holding_id="alt_pe_smith",
                event_type="capital_call",
                amount=Decimal("100000.00"),
                event_date=date(2025, 6, 1),
                notes="Initial capital call",
            )
        )
        session.add(
            AlternativeEventRow(
                event_id="alt_evt_mark_1",
                holding_id="alt_pe_smith",
                event_type="mark",
                amount=Decimal("410000.00"),
                event_date=date(2026, 3, 31),
                notes="Q1 2026 manager mark",
            )
        )


def seed_realized_gain_events(session: Session) -> None:
    """Idempotent demo realized-gain rows for reporting YTD (st6b)."""
    if session.get(RealizedGainEventRow, "rg_ytd_demo"):
        return
    session.add_all(
        [
            RealizedGainEventRow(
                event_id="rg_ytd_demo",
                household_id=DEMO_HOUSEHOLD_ID,
                event_date=date(2026, 3, 15),
                amount=Decimal("4200.00"),
            ),
            RealizedGainEventRow(
                event_id="rg_prior_year",
                household_id=DEMO_HOUSEHOLD_ID,
                event_date=date(2025, 11, 1),
                amount=Decimal("10000.00"),
            ),
        ]
    )


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
        [
            MarketPriceRow(security_id=s, price=p, as_of_date=as_of)
            for s, p in prices
        ]
    )


def _sync_workflow_definitions(session: Session) -> None:
    """Add catalog workflows missing from an existing demo DB."""
    existing = set(session.scalars(select(WorkflowDefinitionRow.name)).all())
    for workflow in WORKFLOW_CATALOG:
        if workflow.name in existing:
            continue
        session.add(
            WorkflowDefinitionRow(
                name=workflow.name,
                owner=workflow.owner,
                inputs=json.dumps(workflow.inputs),
                outputs=json.dumps(workflow.outputs),
                sla_hours=workflow.sla_hours,
            )
        )


def seed_demo_data(session: Session) -> bool:
    """Insert demo graph, securities, lots, workflows.

    Returns True if newly seeded.
    """
    existing = session.scalar(
        select(EntityRow).where(EntityRow.entity_id == DEMO_HOUSEHOLD_ID)
    )
    if existing:
        seed_market_prices(session)
        seed_ips_policy(session)
        seed_demo_lots(session)
        seed_phase4_extensions(session)
        seed_realized_gain_events(session)
        _sync_workflow_definitions(session)
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
        EntityRow(
            entity_id="custodian_fidelity",
            entity_type=EntityType.CUSTODIAN,
            name="Fidelity Investments",
            household_id=None,
        ),
        EntityRow(
            entity_id="acct_fidelity",
            entity_type=EntityType.ACCOUNT,
            name="Fidelity Taxable",
            household_id=DEMO_HOUSEHOLD_ID,
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
        EntityRelationshipRow(
            source_id=DEMO_HOUSEHOLD_ID,
            target_id="acct_fidelity",
            relationship_type=RelationshipType.AGGREGATES,
        ),
        EntityRelationshipRow(
            source_id="trust_smith_rev",
            target_id="acct_fidelity",
            relationship_type=RelationshipType.HOLDS,
        ),
        EntityRelationshipRow(
            source_id="acct_fidelity",
            target_id="custodian_fidelity",
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
            lot_id="lot_vti_2",
            account_id="acct_taxable",
            security_id="sec_vti",
            quantity=Decimal("50"),
            cost_basis_per_share=Decimal("255.00"),
            acquisition_date=date(2025, 3, 1),
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
        LotRow(
            lot_id="lot_fidelity_vti",
            account_id="acct_fidelity",
            security_id="sec_vti",
            quantity=Decimal("200"),
            cost_basis_per_share=Decimal("230.00"),
            acquisition_date=date(2024, 6, 1),
        ),
        LotRow(
            lot_id="lot_fidelity_bnd",
            account_id="acct_fidelity",
            security_id="sec_bnd",
            quantity=Decimal("150"),
            cost_basis_per_share=Decimal("74.00"),
            acquisition_date=date(2023, 11, 15),
        ),
    ]
    alt_holdings = [
        AlternativeHoldingRow(
            holding_id="alt_pe_smith",
            household_id=DEMO_HOUSEHOLD_ID,
            entity_id="trust_smith_rev",
            name="Smith Growth PE Fund II",
            asset_type="private_equity",
            committed_capital=Decimal("500000.00"),
            called_capital=Decimal("350000.00"),
            current_nav=Decimal("410000.00"),
            last_mark_date=date(2026, 3, 31),
        ),
    ]
    alt_events = [
        AlternativeEventRow(
            event_id="alt_evt_call_1",
            holding_id="alt_pe_smith",
            event_type="capital_call",
            amount=Decimal("100000.00"),
            event_date=date(2025, 6, 1),
            notes="Initial capital call",
        ),
        AlternativeEventRow(
            event_id="alt_evt_mark_1",
            holding_id="alt_pe_smith",
            event_type="mark",
            amount=Decimal("410000.00"),
            event_date=date(2026, 3, 31),
            notes="Q1 2026 manager mark",
        ),
    ]
    realized_events = [
        RealizedGainEventRow(
            event_id="rg_ytd_demo",
            household_id=DEMO_HOUSEHOLD_ID,
            event_date=date(2026, 3, 15),
            amount=Decimal("4200.00"),
        ),
        RealizedGainEventRow(
            event_id="rg_prior_year",
            household_id=DEMO_HOUSEHOLD_ID,
            event_date=date(2025, 11, 1),
            amount=Decimal("10000.00"),
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
    session.add_all(alt_holdings)
    session.add_all(alt_events)
    session.add_all(realized_events)
    session.add_all(workflows)
    seed_market_prices(session)
    seed_ips_policy(session)
    return True
