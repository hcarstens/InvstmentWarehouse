"""Shared pytest fixtures."""

import os
from decimal import Decimal

import pytest

from warehouse.config import get_settings
from warehouse.data.ledger import Lot
from warehouse.data.security_master import AssetClass, Security, TaxCharacter
from warehouse.infra.db.bootstrap import bootstrap_database


@pytest.fixture(scope="session", autouse=True)
def isolated_database(tmp_path_factory: pytest.TempPathFactory) -> None:
    db_dir = tmp_path_factory.mktemp("warehouse_db")
    db_file = db_dir / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"
    get_settings.cache_clear()
    bootstrap_database(seed=True)
    yield
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)


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
