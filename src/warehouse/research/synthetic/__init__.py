"""Compositional HNW synthetic portfolio generator (Shape B → Shape A)."""

from warehouse.research.synthetic.asset_test_suite import (
    AssetTestSuiteResult,
    load_asset_test_summary,
    run_asset_test_suite,
)
from warehouse.research.synthetic.cohort import (
    COHORT_IDS,
    GENERATOR_VERSION,
    default_cohort_for_rung,
)
from warehouse.research.synthetic.hnw_asset_types import (
    HNW_ASSET_TYPES,
    HnwAssetSpec,
    HnwAssetType,
    IpsExcludedError,
    hnw_asset_spec,
)
from warehouse.research.synthetic.hnw_manifest import (
    build_manifest_from_hnw_types,
)
from warehouse.research.synthetic.manifest import project_to_asset_portfolio
from warehouse.research.synthetic.models import HouseholdFixture
from warehouse.research.synthetic.pipeline import emit_hnw_fixture
from warehouse.research.synthetic.scenario_card import (
    ScenarioCard,
    build_scenario_card,
    write_scenario_card,
)
from warehouse.research.synthetic.stress_harness import (
    HarnessCell,
    iter_hnw_combinations,
    run_combination_matrix,
    run_harness_cell,
    summarize_matrix,
)

__all__ = [
    "COHORT_IDS",
    "GENERATOR_VERSION",
    "HNW_ASSET_TYPES",
    "AssetTestSuiteResult",
    "HarnessCell",
    "HouseholdFixture",
    "HnwAssetType",
    "HnwAssetSpec",
    "IpsExcludedError",
    "ScenarioCard",
    "build_manifest_from_hnw_types",
    "build_scenario_card",
    "default_cohort_for_rung",
    "emit_hnw_fixture",
    "hnw_asset_spec",
    "iter_hnw_combinations",
    "load_asset_test_summary",
    "project_to_asset_portfolio",
    "run_asset_test_suite",
    "run_combination_matrix",
    "run_harness_cell",
    "summarize_matrix",
    "write_scenario_card",
]
