"""Shared pytest fixtures."""

from decimal import Decimal

import pytest

from warehouse.data.ledger import Lot
from warehouse.data.security_master import AssetClass, Security, TaxCharacter


@pytest.fixture
def sample_security() -> Security:
    return Security(
        security_id="sec_vti",
        ticker="VTI",
        cusip="922908769",
        name="Vanguard Total Stock Market ETF",
        asset_class=AssetClass.ETF,
        tax_character=TaxCharacter.LTCG,
        wash_sale_substitute_group="us_equity_broad",
    )


@pytest.fixture
def sample_lot() -> Lot:
    return Lot(
        lot_id="lot_001",
        account_id="acct_taxable_01",
        security_id="sec_vti",
        quantity=Decimal("100"),
        cost_basis_per_share=Decimal("220.50"),
        acquisition_date="2024-03-15",
    )
