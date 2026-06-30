"""Registry of types that must reject in-place mutation (no silent no-ops)."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, is_dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError

from warehouse.config import Settings
from warehouse.data.security_master import AssetClass as SecurityAssetClass
from warehouse.decision.analyst import (
    AnalystCheckpoint,
    AnalystCheckpointScore,
    AnalystReview,
    AttributionReport,
    KillBreach,
    KillCriteria,
    KillCriterion,
    NpaFlag,
    NpaFlags,
    NpaReason,
    NpaSubject,
    PositionAttribution,
    PositionThesis,
)
from warehouse.decision.ips.monitor import IpsDriftReport
from warehouse.decision.ips.sleeves import IpsSleeve
from warehouse.decision.optimizer import OptimizationResult
from warehouse.decision.optimizer.models import RebalanceProposal
from warehouse.decision.tax.scenarios import (
    TaxScenarioOverlays,
    TaxScenarioResult,
)
from warehouse.messaging.models import DispatchContext, Kind, Message
from warehouse.messaging.payloads import AdviceBundle, AxiomScore, PmNarrative
from warehouse.models.events import Event, EventType
from warehouse.orchestrator.models import (
    OrchestratorError,
    OrchestratorIntent,
    OrchestratorResponse,
)
from warehouse.reporting.performance import (
    HouseholdPerformanceReport,
    RealizedGainEvent,
)
from warehouse.reporting.report_writer.models import (
    ComparisonDelta,
    ReportBundle,
    ReportComparison,
    ReportPeriod,
    WrittenHouseholdReport,
)
from warehouse.reporting.tax import ReportingTaxResult
from warehouse.research.backtest import BacktestResult
from warehouse.research.risk.engine import evaluate_portfolio_risk
from warehouse.research.risk.models import (
    AllocationSlot,
    AssetClass,
    AssetPortfolio,
    MetricDelta,
    RiskDeltas,
    RiskHorizon,
    RiskRequest,
    RiskResult,
    ScenarioSet,
)
from warehouse.research.synthetic.daily_paths import PathTargets
from warehouse.workflows.month_end import (
    MonthEndHouseholdOutcome,
    MonthEndReportingResult,
)

# Append new audit/replay-critical immutable types here.
FROZEN_TYPES: tuple[type[Any], ...] = (
    AdviceBundle,
    AnalystCheckpoint,
    AnalystReview,
    AttributionReport,
    BacktestResult,
    ComparisonDelta,
    DispatchContext,
    Event,
    HouseholdPerformanceReport,
    KillBreach,
    KillCriteria,
    Message,
    MonthEndHouseholdOutcome,
    MonthEndReportingResult,
    NpaFlag,
    NpaFlags,
    OptimizationResult,
    OrchestratorError,
    OrchestratorResponse,
    PathTargets,
    PmNarrative,
    PositionAttribution,
    PositionThesis,
    RebalanceProposal,
    RealizedGainEvent,
    ReportBundle,
    ReportComparison,
    ReportingTaxResult,
    RiskDeltas,
    RiskResult,
    Settings,
    WrittenHouseholdReport,
)


def _sample_instance(cls: type[Any]) -> Any:
    if cls is BacktestResult:
        return BacktestResult(
            run_id="run_test",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            after_tax_return=Decimal("0.05"),
            baseline_after_tax_return=Decimal("0.04"),
            tax_delta=Decimal("0.01"),
            config_hash="abc123",
            input_snapshot_id="snap_test",
        )
    if cls is Event:
        return Event(
            event_id="evt_test",
            account_id="acct_test",
            event_type=EventType.TRADE,
            occurred_at=datetime(2024, 6, 1, tzinfo=UTC),
        )
    if cls is Settings:
        return Settings()
    if cls is Message:
        return Message(
            op="messaging.ping",
            kind=Kind.QUERY,
            payload=RiskHorizon(years=Decimal("5")),
            correlation_id="corr_test",
        )
    if cls is DispatchContext:
        # Frozen dataclass — no runtime type check; a real Session is not
        # needed to prove setattr is rejected.
        return DispatchContext(session=None)  # type: ignore[arg-type]
    if cls is RiskResult:
        portfolio = AssetPortfolio(
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("1"),
                )
            ],
        )
        request = RiskRequest(
            horizon=RiskHorizon(years=Decimal("5")),
            run_scenarios=ScenarioSet.NONE,
        )
        report = evaluate_portfolio_risk(portfolio, request.horizon)
        return RiskResult(report=report, scenarios={}, deltas=None)
    if cls is RiskDeltas:
        return RiskDeltas(
            overlay_label="demo",
            baseline_fingerprint="baseline",
            proposed_fingerprint="proposed",
            headline=[
                MetricDelta(
                    metric="annualized_volatility",
                    baseline=Decimal("0.10"),
                    proposed=Decimal("0.11"),
                    delta=Decimal("0.01"),
                    pct_change=Decimal("0.10"),
                )
            ],
            by_class_variance_delta={"equity": Decimal("0.02")},
        )
    if cls is PmNarrative:
        return PmNarrative(
            correlation_id="corr_test",
            axioms_scored={"axiom_1": AxiomScore.PASS},
            headline="test headline",
            specialist_status={"risk": "live", "tax": "stub"},
        )
    if cls is AdviceBundle:
        portfolio = AssetPortfolio(
            allocations=[
                AllocationSlot(
                    asset_class=AssetClass.EQUITY,
                    weight=Decimal("1"),
                )
            ],
        )
        request = RiskRequest(
            horizon=RiskHorizon(years=Decimal("5")),
            run_scenarios=ScenarioSet.NONE,
        )
        report = evaluate_portfolio_risk(portfolio, request.horizon)
        risk = RiskResult(report=report, scenarios={}, deltas=None)
        zero = Decimal("0")
        return AdviceBundle(
            risk=risk,
            proposal=OptimizationResult(
                household_id="hh_test",
                config_version="test",
                trades=[],
                estimated_tax_delta=zero,
            ),
            tax=TaxScenarioResult(
                overlays=TaxScenarioOverlays(),
                baseline_tax=zero,
                scenario_tax=zero,
                tax_delta=zero,
            ),
            drift=IpsDriftReport(
                household_id="hh_test",
                rows=[],
                alerts=[],
                concentration_alerts=[],
            ),
            narrative=None,
        )
    if cls is PositionAttribution:
        return _sample_position_attribution()
    if cls is AttributionReport:
        return AttributionReport(
            household_id="hh_test",
            as_of_date=date(2026, 6, 28),
            config_version="2026.06",
            positions=[_sample_position_attribution()],
            portfolio_active_return=Decimal("-0.08"),
            limitations=["unrealized point-in-time only"],
        )
    if cls is AnalystCheckpoint:
        return AnalystCheckpoint(
            checkpoint_id="checkpoint_2",
            score=AnalystCheckpointScore.PASS,
            detail="test detail",
        )
    if cls is AnalystReview:
        return AnalystReview(
            config_version="2026.06",
            checkpoints={"checkpoint_2": AnalystCheckpointScore.PASS},
            details={"checkpoint_2": "test detail"},
            headline="test headline",
        )
    if cls is KillCriteria:
        return KillCriteria(max_drawdown_vs_cost=Decimal("-0.20"))
    if cls is PositionThesis:
        return PositionThesis(
            account_id="acct_test",
            instrument="AAPL",
            mechanism="test thesis",
            effective_date=date(2020, 1, 1),
            kill_criteria=KillCriteria(max_drawdown_vs_cost=Decimal("-0.20")),
            config_version="2026.06",
        )
    if cls is KillBreach:
        return KillBreach(
            account_id="acct_test",
            instrument="AAPL",
            criterion=KillCriterion.DRAWDOWN_VS_COST,
            observed=Decimal("-0.25"),
            threshold=Decimal("-0.20"),
            detail="test breach",
        )
    if cls is NpaFlag:
        return _sample_npa_flag()
    if cls is NpaFlags:
        return NpaFlags(
            household_id="hh_test",
            as_of_date=date(2026, 6, 28),
            config_version="2026.06",
            flags=[_sample_npa_flag()],
            limitations=["advisory only"],
        )
    if cls is RebalanceProposal:
        return _sample_rebalance_proposal()
    if cls is OptimizationResult:
        return OptimizationResult(
            household_id="hh_test",
            config_version="test",
            trades=[],
            estimated_tax_delta=Decimal("0"),
            rebalance=_sample_rebalance_proposal(),
        )
    if cls is OrchestratorError:
        return OrchestratorError(
            correlation_id="corr_test",
            message="test failure",
        )
    if cls is OrchestratorResponse:
        return OrchestratorResponse(
            correlation_id="corr_test",
            intent=OrchestratorIntent.REBALANCE_ADVISORY,
            household_id="hh_test",
            status="failed",
            error=OrchestratorError(
                correlation_id="corr_test",
                message="test failure",
            ),
            elapsed_ms=0,
        )
    if cls is PathTargets:
        return PathTargets(
            annual_vol=0.16,
            lag1_autocorr=0.05,
            excess_kurtosis=1.5,
            vol_clustering=0.97,
        )
    if cls is HouseholdPerformanceReport:
        return HouseholdPerformanceReport(
            household_id="hh_test",
            as_of_date="2026-06-24",
            total_market_value=Decimal("1000000"),
            unrealized_gain=Decimal("50000"),
            realized_gain_ytd=Decimal("12000"),
        )
    if cls is RealizedGainEvent:
        return RealizedGainEvent(
            event_id="evt_realized_test",
            event_date=date(2026, 3, 1),
            amount=Decimal("12000"),
        )
    if cls is ReportingTaxResult:
        return ReportingTaxResult(
            overlays=TaxScenarioOverlays(),
            baseline_tax=Decimal("1000"),
            scenario_tax=Decimal("1100"),
            tax_delta=Decimal("100"),
        )
    if cls is ComparisonDelta:
        return ComparisonDelta(
            label="total_market_value",
            current=Decimal("1000000"),
            prior=Decimal("950000"),
            abs_delta=Decimal("50000"),
            pct_delta=Decimal("0.0526"),
        )
    if cls is ReportComparison:
        return ReportComparison(
            prior_snapshot_id="rpt_prior",
            prior_as_of_date=date(2026, 5, 31),
            is_adjacent=True,
            performance=(_sample_instance(ComparisonDelta),),
            drift=(),
        )
    if cls is ReportBundle:
        return ReportBundle(
            snapshot_id="rpt_test",
            household_id="hh_test",
            period=ReportPeriod.month_end(date(2026, 6, 24)),
            as_of_date=date(2026, 6, 24),
            generated_at=datetime(2026, 6, 24, tzinfo=UTC),
            performance=HouseholdPerformanceReport(
                household_id="hh_test",
                as_of_date="2026-06-24",
                total_market_value=Decimal("1000000"),
                unrealized_gain=Decimal("50000"),
                realized_gain_ytd=Decimal("12000"),
            ),
            ips_drift=IpsDriftReport(
                household_id="hh_test",
                rows=[],
                alerts=[],
                concentration_alerts=[],
            ),
            tax_scenarios=(
                ReportingTaxResult(
                    overlays=TaxScenarioOverlays(),
                    baseline_tax=Decimal("0"),
                    scenario_tax=Decimal("0"),
                    tax_delta=Decimal("0"),
                ),
            ),
            staged_orders=(),
            pending_approval_count=0,
            open_breaks=(),
            limitations=("test limitation",),
            data_sources=("reporting.performance:test",),
        )
    if cls is WrittenHouseholdReport:
        return WrittenHouseholdReport(
            snapshot_id="rpt_test",
            household_id="hh_test",
            period_label="month-end-2026-06-24",
            as_of_date=date(2026, 6, 24),
            generated_at=datetime(2026, 6, 24, tzinfo=UTC),
            output_dir="/tmp/reports/hh_test/month-end-2026-06-24/rpt_test",
            internal_markdown_path=(
                "/tmp/reports/hh_test/month-end-2026-06-24/rpt_test/internal.md"
            ),
            external_markdown_path=(
                "/tmp/reports/hh_test/month-end-2026-06-24/rpt_test/external.md"
            ),
            bundle_json_path=(
                "/tmp/reports/hh_test/month-end-2026-06-24/rpt_test/bundle.json"
            ),
            external_pdf_path=(
                "/tmp/reports/hh_test/month-end-2026-06-24/rpt_test/external.pdf"
            ),
            external_pdf_sha256="abc123",
        )
    if cls is MonthEndHouseholdOutcome:
        return MonthEndHouseholdOutcome(
            household_id="hh_test",
            status="completed",
            written=_sample_instance(WrittenHouseholdReport),
        )
    if cls is MonthEndReportingResult:
        return MonthEndReportingResult(
            as_of_date=date(2026, 6, 24),
            correlation_id="month_end_batch_test",
            started_at=datetime(2026, 6, 24, tzinfo=UTC),
            finished_at=datetime(2026, 6, 24, tzinfo=UTC),
            outcomes=(_sample_instance(MonthEndHouseholdOutcome),),
        )
    raise TypeError(f"No sample factory for frozen type {cls!r}")


def _sample_rebalance_proposal() -> RebalanceProposal:
    return RebalanceProposal(
        target_weights={IpsSleeve.EQUITY: Decimal("1")},
        current_weights={IpsSleeve.EQUITY: Decimal("1")},
        delta_w={IpsSleeve.EQUITY: Decimal("0")},
        policy_drift={IpsSleeve.EQUITY: Decimal("0")},
        binding_bounds=[],
        unbounded_sleeves=[IpsSleeve.EQUITY],
        illiquid_advisory_sleeves=[],
        risk_contributions={IpsSleeve.EQUITY: Decimal("1")},
        turnover_l1=Decimal("0"),
        objective_value=Decimal("0.07"),
        lam=Decimal("6.0"),
        config_version="2026.06",
        # po2 scenario-robust stress overlay (§B.8) — additive fields.
        stress_regime="high_risk",
        stress_target_weights={IpsSleeve.EQUITY: Decimal("1")},
        stress_delta_w={IpsSleeve.EQUITY: Decimal("0")},
        regime_gap_l1=Decimal("0"),
        stress_objective_value=Decimal("0.05"),
        stress_risk_contributions={IpsSleeve.EQUITY: Decimal("1")},
    )


def _sample_npa_flag() -> NpaFlag:
    return NpaFlag(
        subject=NpaSubject.POSITION,
        subject_id="lot_test",
        label="AAPL",
        reason=NpaReason.SUSTAINED_DRAWDOWN,
        observed=Decimal("-0.14"),
        threshold=Decimal("-0.10"),
        detail="test flag",
    )


def _sample_position_attribution() -> PositionAttribution:
    return PositionAttribution(
        lot_id="lot_test",
        account_id="acct_test",
        ticker="VTI",
        security_asset_class=SecurityAssetClass.ETF,
        risk_class=AssetClass.EQUITY,
        liquidity_tier=1,
        holding_years=Decimal("2.45"),
        market_value=Decimal("100"),
        total_return=Decimal("0.10"),
        class_expected=Decimal("0.07"),
        expected_cumulative=Decimal("0.18"),
        active_return=Decimal("-0.08"),
        active_annualized=Decimal("-0.03"),
    )


def _mutation_probe_attr(instance: Any) -> str:
    if isinstance(instance, BacktestResult):
        return "run_id"
    if isinstance(instance, Event):
        return "event_id"
    if isinstance(instance, Settings):
        return "app_env"
    if isinstance(instance, RiskResult):
        return "deltas"
    if isinstance(instance, RiskDeltas):
        return "overlay_label"
    if isinstance(instance, PmNarrative):
        return "headline"
    if isinstance(instance, AdviceBundle):
        return "narrative"
    if isinstance(instance, PositionAttribution):
        return "lot_id"
    if isinstance(instance, AttributionReport):
        return "household_id"
    if isinstance(instance, AnalystCheckpoint):
        return "detail"
    if isinstance(instance, AnalystReview):
        return "headline"
    if isinstance(instance, KillCriteria):
        return "max_drawdown_vs_cost"
    if isinstance(instance, PositionThesis):
        return "mechanism"
    if isinstance(instance, KillBreach):
        return "detail"
    if isinstance(instance, NpaFlag):
        return "detail"
    if isinstance(instance, NpaFlags):
        return "household_id"
    if isinstance(instance, RebalanceProposal):
        return "turnover_l1"
    if isinstance(instance, OptimizationResult):
        return "household_id"
    if isinstance(instance, OrchestratorError):
        return "message"
    if isinstance(instance, OrchestratorResponse):
        return "status"
    if isinstance(instance, Message):
        return "op"
    if isinstance(instance, DispatchContext):
        return "actor_id"
    if isinstance(instance, PathTargets):
        return "annual_vol"
    if isinstance(instance, HouseholdPerformanceReport):
        return "household_id"
    if isinstance(instance, RealizedGainEvent):
        return "amount"
    if isinstance(instance, ReportingTaxResult):
        return "tax_delta"
    if isinstance(instance, ComparisonDelta):
        return "label"
    if isinstance(instance, ReportComparison):
        return "prior_snapshot_id"
    if isinstance(instance, ReportBundle):
        return "snapshot_id"
    if isinstance(instance, WrittenHouseholdReport):
        return "snapshot_id"
    if isinstance(instance, MonthEndHouseholdOutcome):
        return "household_id"
    if isinstance(instance, MonthEndReportingResult):
        return "correlation_id"
    raise TypeError(f"No mutation probe for {type(instance)!r}")


def assert_rejects_mutation(
    instance: Any, attr: str | None = None, value: Any = "mutated"
) -> None:
    """Raise AssertionError if setattr succeeds (silent mutation)."""
    field = attr or _mutation_probe_attr(instance)
    try:
        setattr(instance, field, value)
    except (FrozenInstanceError, ValidationError, TypeError):
        return
    raise AssertionError(
        f"{type(instance).__name__}.{field} accepted mutation — "
        f"type must be frozen "
        f"(frozen dataclass or pydantic ConfigDict(frozen=True))"
    )


def frozen_type_samples() -> list[tuple[type[Any], Any]]:
    return [(cls, _sample_instance(cls)) for cls in FROZEN_TYPES]


def is_registered_frozen_type(cls: type[Any]) -> bool:
    if cls in FROZEN_TYPES:
        return True
    dc_params = getattr(cls, "__dataclass_params__", None)
    if is_dataclass(cls) and dc_params is not None and dc_params.frozen:
        return True
    if issubclass(cls, BaseModel) and cls.model_config.get("frozen"):
        return True
    return False
