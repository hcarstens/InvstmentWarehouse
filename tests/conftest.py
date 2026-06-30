"""Shared pytest fixtures."""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import HealthCheck, settings

from warehouse.data.ledger import Lot
from warehouse.data.security_master import AssetClass, Security, TaxCharacter
from warehouse.infra.db.bootstrap import bootstrap_database

_FAKE_PDF = b"%PDF-1.4\n% fake report writer test pdf\n"

# Deterministic property tests in the gate. ``derandomize=True`` makes @given
# replay the same examples every run, so a push never randomly fails on a fresh
# input Hypothesis just discovered. ``deadline=None`` removes timing-based
# flakes (slow machine -> DeadlineExceeded). This is the real fix for the
# intermittent "QP property flakes" -- not widening input floors. Loaded
# unconditionally so local and CI runs are identical.
settings.register_profile(
    "warehouse",
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.load_profile("warehouse")


@pytest.fixture(scope="session", autouse=True)
def _session_bootstrap_database() -> None:
    """Migrate + seed once per pytest session (CI and local parity)."""
    bootstrap_database(seed=True)


@pytest.fixture
def sample_security() -> Security:
    return Security(
        security_id="sec_vti",
        ticker="VTI",
        name="Vanguard Total Stock Market ETF",
        asset_class=AssetClass.ETF,
        tax_character=TaxCharacter.LTCG,
        wash_sale_substitute_group="us_equity_broad",
    )


@pytest.fixture
def sample_lot() -> Lot:
    return Lot(
        lot_id="lot_vti",
        account_id="acct_taxable",
        security_id="sec_vti",
        quantity=Decimal("100"),
        cost_basis_per_share=Decimal("220.50"),
        acquisition_date=date(2024, 1, 15),
    )


def _fake_pdf_render(
    external_md_path: Path,
    *,
    output_pdf_path: Path,
    snapshot_id: str,
) -> str:
    del external_md_path, snapshot_id
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)
    output_pdf_path.write_bytes(_FAKE_PDF)
    return hashlib.sha256(_FAKE_PDF).hexdigest()


@pytest.fixture(autouse=True)
def _mock_report_pdf_render_unless_pandoc(request, monkeypatch) -> None:
    if request.node.get_closest_marker("pandoc"):
        return
    monkeypatch.setattr(
        "warehouse.reporting.report_writer.writer.render_external_pdf",
        _fake_pdf_render,
    )
