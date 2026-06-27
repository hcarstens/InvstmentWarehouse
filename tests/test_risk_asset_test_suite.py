"""Risk asset test suite — Phase A/B report writing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from warehouse.research.synthetic.asset_test_suite import (
    load_asset_test_summary,
    run_asset_test_suite,
)


@pytest.fixture
def reports_tmp(tmp_path: Path) -> Path:
    return tmp_path / "risk_asset_tests"


def test_phase_a_writes_reports_and_summary(reports_tmp: Path) -> None:
    suite = run_asset_test_suite("A", reports_dir=reports_tmp)
    assert suite.cells_run == 15
    assert suite.summary["ok"] == 13
    assert suite.summary["ips_excluded"] == 2
    assert suite.summary["error"] == 0
    assert (reports_tmp / "phase_a_summary.json").is_file()
    ok_cell = next(c for c in suite.cells if c.status == "ok")
    assert ok_cell.report_path is not None
    report_file = reports_tmp / "phase_a" / "public_equity.json"
    assert report_file.is_file()
    body = json.loads(report_file.read_text())
    assert body["status"] == "ok"
    assert "risk_eval" in body
    assert "level_1_portfolio" in body["risk_eval"]


def test_phase_b_pairs_writes_reports(reports_tmp: Path) -> None:
    suite = run_asset_test_suite(
        "B",
        reports_dir=reports_tmp,
        phase_b_max_size=2,
    )
    assert suite.cells_run == 105
    assert suite.summary["error"] == 0
    assert (reports_tmp / "phase_b_summary.json").is_file()
    pair_cell = next(c for c in suite.cells if c.combination_size == 2)
    assert pair_cell.report_path is not None
    assert "__" in pair_cell.report_path


def test_cell_filename_hashed_when_combination_too_long() -> None:
    from warehouse.research.synthetic.asset_test_suite import _cell_filename
    from warehouse.research.synthetic.hnw_asset_types import HNW_ASSET_TYPES

    all_types = tuple(t.value for t in HNW_ASSET_TYPES)
    name = _cell_filename(all_types)
    assert len(name) <= 255
    assert name.startswith("n15_")
    assert name.endswith(".json")
    assert _cell_filename((all_types[0],)) == f"{all_types[0]}.json"


def test_load_summary_round_trip(reports_tmp: Path) -> None:
    run_asset_test_suite("A", reports_dir=reports_tmp)
    loaded = load_asset_test_summary("A", reports_dir=reports_tmp)
    assert loaded is not None
    assert loaded.cells_run == 15
