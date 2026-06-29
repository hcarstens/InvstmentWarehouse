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
from warehouse.research.synthetic.ips_cohort import COHORT_IPS_PRIORS
from warehouse.research.synthetic.ips_emit import emit_ips_for_cohort
from warehouse.research.synthetic.ips_validate import (
    IpsValidationError,
    validate_ips,
)
from warehouse.research.synthetic.manifest import project_to_asset_portfolio
from warehouse.research.synthetic.models import (
    HouseholdFixture,
    IpsValidationResult,
    SyntheticHouseholdBundle,
)
from warehouse.research.synthetic.pipeline import (
    emit_hnw_fixture,
    emit_synthetic_household,
)
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
from warehouse.research.synthetic.thesis_emit import (
    emit_synthetic_theses,
    synthetic_thesis_as_of,
)
from warehouse.research.synthetic.workflow_smoke import (
    E2eMatrixResult,
    WorkflowSmokeCheck,
    WorkflowSmokeResult,
    run_e2e_matrix,
    run_workflow_smoke,
)

__all__ = [
    "COHORT_IDS",
    "COHORT_IPS_PRIORS",
    "GENERATOR_VERSION",
    "HNW_ASSET_TYPES",
    "AssetTestSuiteResult",
    "HarnessCell",
    "HouseholdFixture",
    "HnwAssetType",
    "HnwAssetSpec",
    "IpsValidationError",
    "IpsValidationResult",
    "IpsExcludedError",
    "E2eMatrixResult",
    "ScenarioCard",
    "SyntheticHouseholdBundle",
    "build_manifest_from_hnw_types",
    "build_scenario_card",
    "default_cohort_for_rung",
    "emit_hnw_fixture",
    "emit_ips_for_cohort",
    "emit_synthetic_household",
    "emit_synthetic_theses",
    "synthetic_thesis_as_of",
    "hnw_asset_spec",
    "iter_hnw_combinations",
    "load_asset_test_summary",
    "project_to_asset_portfolio",
    "run_asset_test_suite",
    "run_combination_matrix",
    "run_e2e_matrix",
    "run_harness_cell",
    "run_workflow_smoke",
    "summarize_matrix",
    "validate_ips",
    "WorkflowSmokeCheck",
    "WorkflowSmokeResult",
    "write_scenario_card",
]
