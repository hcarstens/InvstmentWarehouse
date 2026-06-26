"""Compositional HNW synthetic portfolio generator (Shape B → Shape A)."""

from warehouse.research.synthetic.cohort import (
    COHORT_IDS,
    GENERATOR_VERSION,
    default_cohort_for_rung,
)
from warehouse.research.synthetic.manifest import project_to_asset_portfolio
from warehouse.research.synthetic.models import HouseholdFixture
from warehouse.research.synthetic.pipeline import emit_hnw_fixture
from warehouse.research.synthetic.scenario_card import (
    ScenarioCard,
    build_scenario_card,
    write_scenario_card,
)

__all__ = [
    "COHORT_IDS",
    "GENERATOR_VERSION",
    "HouseholdFixture",
    "ScenarioCard",
    "build_scenario_card",
    "default_cohort_for_rung",
    "emit_hnw_fixture",
    "project_to_asset_portfolio",
    "write_scenario_card",
]
