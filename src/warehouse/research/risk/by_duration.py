"""Risk evaluation by duration bucket and horizon mismatch."""

from __future__ import annotations

from decimal import Decimal

from warehouse.research.risk.models import (
    AllocationSlot,
    ClassRiskContribution,
    DurationBucketRisk,
    RiskHorizon,
)


def _duration_bucket(years: Decimal | None) -> str:
    if years is None:
        return "undefined"
    if years < Decimal("3"):
        return "short"
    if years <= Decimal("7"):
        return "medium"
    return "long"


def evaluate_duration_risk(
    slots: list[AllocationSlot],
    horizon: RiskHorizon,
    class_contributions: list[ClassRiskContribution],
) -> list[DurationBucketRisk]:
    buckets: dict[str, list[AllocationSlot]] = {}
    for slot in slots:
        bucket = _duration_bucket(slot.duration_years)
        buckets.setdefault(bucket, []).append(slot)

    contrib_by_class = {c.asset_class: c.risk_contribution for c in class_contributions}
    results: list[DurationBucketRisk] = []

    for bucket_name, members in sorted(buckets.items()):
        weight = sum((m.weight for m in members), Decimal("0"))
        durations = [m.duration_years for m in members if m.duration_years is not None]
        avg_duration = (
            sum(durations, Decimal("0")) / Decimal(len(durations)) if durations else None
        )
        mismatch = Decimal("0")
        if avg_duration is not None and horizon.years > 0:
            mismatch = abs(avg_duration - horizon.years) / horizon.years
        bucket_risk = sum(
            (contrib_by_class.get(m.asset_class.value, Decimal("0")) for m in members),
            Decimal("0"),
        )
        results.append(
            DurationBucketRisk(
                bucket=bucket_name,
                weight=weight,
                avg_duration_years=avg_duration,
                horizon_mismatch=mismatch,
                risk_contribution=bucket_risk,
            )
        )
    return results
