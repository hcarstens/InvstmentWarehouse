"""Render frozen ReportBundle to audience-specific Markdown."""

from __future__ import annotations

from decimal import Decimal

from warehouse.reporting.report_writer.models import (
    ReportAudience,
    ReportBundle,
)

_TAX_SCENARIO_LABELS: tuple[str, ...] = ("baseline", "niit_overlay")


def _fmt_money(value: Decimal) -> str:
    return f"${value:,.2f}"


def _after_tax_display(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def _yaml_front_matter(
    bundle: ReportBundle,
    *,
    audience: ReportAudience,
    classification: str,
) -> str:
    lines = [
        "---",
        f"title: Household Report — {bundle.household_id}",
        f"date: {bundle.as_of_date.isoformat()}",
        f"audience: {audience.value}",
        f"classification: {classification}",
        f"period: {bundle.period.label}",
        f"snapshot_id: {bundle.snapshot_id}",
    ]
    if audience == ReportAudience.INTERNAL:
        window_end = bundle.period.end_date or bundle.as_of_date
        window_start = bundle.period.start_date
        if window_start is not None:
            window = f"{window_start.isoformat()} to {window_end.isoformat()}"
        else:
            window = f"through {window_end.isoformat()}"
        lines.append(f"reporting_window: {window}")
    lines.append("---")
    return "\n".join(lines)


def _performance_table(bundle: ReportBundle) -> str:
    perf = bundle.performance
    if perf is None:
        return "_Performance data unavailable._\n"
    return (
        "| Metric | Value |\n"
        "| --- | --- |\n"
        f"| Total market value | {_fmt_money(perf.total_market_value)} |\n"
        f"| Unrealized gain | {_fmt_money(perf.unrealized_gain)} |\n"
        f"| Realized gain YTD | {_fmt_money(perf.realized_gain_ytd)} |\n"
        f"| After-tax return YTD | "
        f"{_after_tax_display(perf.after_tax_return_ytd)} |\n"
    )


def _ips_in_band(bundle: ReportBundle) -> bool:
    drift = bundle.ips_drift
    if drift is None:
        return True
    return not drift.alerts and not drift.concentration_alerts


def _external_bluf(bundle: ReportBundle) -> str:
    perf = bundle.performance
    if perf is None:
        return (
            "Performance snapshot is unavailable for this period "
            "(see limitations).\n"
        )
    after_tax = _after_tax_display(perf.after_tax_return_ytd)
    policy_note = (
        "Policy allocation is within IPS bands (Exhibit B)."
        if _ips_in_band(bundle)
        else "IPS sleeve or concentration breaches require review (Exhibit B)."
    )
    tax_note = (
        "Tax scenario rollups are shown in Exhibit C; deltas may be "
        "zero-stubbed pending the estimate engine."
    )
    return (
        f"As of {bundle.as_of_date.isoformat()}, total portfolio market value "
        f"is {_fmt_money(perf.total_market_value)} (Exhibit A). "
        f"Unrealized gain is {_fmt_money(perf.unrealized_gain)} and "
        f"realized gain YTD is {_fmt_money(perf.realized_gain_ytd)} "
        f"(Exhibit A); after-tax return YTD is {after_tax} (Exhibit A). "
        f"{policy_note} {tax_note}\n"
    )


def _internal_headline(bundle: ReportBundle) -> str:
    perf = bundle.performance
    drift = bundle.ips_drift
    sleeve_alerts = len(drift.alerts) if drift else 0
    conc_alerts = len(drift.concentration_alerts) if drift else 0
    mv_text = (
        _fmt_money(perf.total_market_value) if perf is not None else "n/a"
    )
    return (
        f"Advisory headline — MV {mv_text} (Exhibit A). "
        f"IPS sleeve alerts: {sleeve_alerts}; concentration alerts: "
        f"{conc_alerts}. Pending approvals: {bundle.pending_approval_count}. "
        f"Open reconciliation breaks (firm-wide): "
        f"{len(bundle.open_breaks)}.\n"
    )


def _exhibit_b_external(bundle: ReportBundle) -> str:
    drift = bundle.ips_drift
    if drift is None:
        return "_Policy alignment data unavailable._\n"
    if _ips_in_band(bundle):
        return (
            "Policy allocation is within IPS bands — no breaches to report.\n"
        )
    lines: list[str] = []
    if drift.alerts:
        lines.append("**Sleeve breaches:**")
        lines.extend(f"- {alert}" for alert in drift.alerts)
    if drift.concentration_alerts:
        lines.append("**Concentration breaches:**")
        lines.extend(f"- {alert}" for alert in drift.concentration_alerts)
    return "\n".join(lines) + "\n"


def _exhibit_b_internal(bundle: ReportBundle) -> str:
    drift = bundle.ips_drift
    if drift is None:
        return "_IPS drift data unavailable._\n"
    lines = [
        "| Sleeve | Current | Target | Min | Max | Drift |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in drift.rows:
        lines.append(
            f"| {row.asset_class} | {row.current_weight:.2%} | "
            f"{row.target_weight:.2%} | {row.min_weight:.2%} | "
            f"{row.max_weight:.2%} | {row.drift:+.2%} |"
        )
    lines.append("")
    if drift.alerts:
        lines.append("**Sleeve alerts:**")
        lines.extend(f"- {alert}" for alert in drift.alerts)
    if drift.concentration_alerts:
        lines.append("**Concentration alerts:**")
        lines.extend(f"- {alert}" for alert in drift.concentration_alerts)
    if not drift.alerts and not drift.concentration_alerts:
        lines.append("_No sleeve or concentration alerts._")
    return "\n".join(lines) + "\n"


def _tax_table(bundle: ReportBundle) -> str:
    if not bundle.tax_scenarios:
        return "_No tax scenarios computed._\n"
    lines = [
        "| Scenario | Baseline tax | Scenario tax | Delta |",
        "| --- | --- | --- | --- |",
    ]
    for idx, scenario in enumerate(bundle.tax_scenarios):
        label = (
            _TAX_SCENARIO_LABELS[idx]
            if idx < len(_TAX_SCENARIO_LABELS)
            else f"scenario_{idx + 1}"
        )
        lines.append(
            f"| {label} | {_fmt_money(scenario.baseline_tax)} | "
            f"{_fmt_money(scenario.scenario_tax)} | "
            f"{_fmt_money(scenario.tax_delta)} |"
        )
    return "\n".join(lines) + "\n"


_APPENDIX_POINTER = (
    "Machine-readable source: `bundle.json` in the report output directory."
)


def _limitations_section(bundle: ReportBundle) -> str:
    lines = ["## Limitations", ""]
    lines.extend(f"- {item}" for item in bundle.limitations)
    return "\n".join(lines) + "\n"


def _execution_section(bundle: ReportBundle) -> str:
    lines = [
        "## Execution & operations",
        "",
        f"Pending advisor approvals: **{bundle.pending_approval_count}**.",
        "",
        "_Reconciliation breaks below are firm-wide, not household-scoped._",
        "",
    ]
    if bundle.staged_orders:
        lines.extend(
            [
                "**Staged orders:**",
                "",
                "| Order | Security | Side | Qty | Status |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for order in bundle.staged_orders:
            lines.append(
                f"| {order.order_id} | {order.security_id} | {order.side} | "
                f"{order.quantity} | {order.status} |"
            )
    else:
        lines.append("_No staged orders._")
    lines.append("")
    if bundle.open_breaks:
        lines.extend(
            [
                "**Open reconciliation breaks (firm-wide):**",
                "",
                "| Break | Account | Description |",
                "| --- | --- | --- |",
            ]
        )
        for brk in bundle.open_breaks:
            lines.append(
                f"| {brk.break_id} | {brk.account_id} | {brk.description} |"
            )
    else:
        lines.append("_No open reconciliation breaks._")
    return "\n".join(lines) + "\n"


def _implications_checklist() -> str:
    return (
        "## Implications\n"
        "\n"
        "- [ ] Review IPS alerts and concentration flags\n"
        "- [ ] Resolve open reconciliation breaks before client delivery\n"
        "- [ ] Obtain advisor attestation on external pack before delivery\n"
    )


def _render_external(bundle: ReportBundle) -> str:
    parts = [
        _yaml_front_matter(
            bundle,
            audience=ReportAudience.EXTERNAL,
            classification="client-facing",
        ),
        "",
        "## Executive summary (BLUF)",
        "",
        _external_bluf(bundle),
        "",
        "## Exhibit A — Performance",
        "",
        _performance_table(bundle),
        "",
        "## Exhibit B — Policy alignment",
        "",
        _exhibit_b_external(bundle),
        "",
        "## Exhibit C — Tax summary",
        "",
        _tax_table(bundle),
        "",
        "_Tax scenario deltas may be illustrative stubs — not for client "
        "filing._",
        "",
        _limitations_section(bundle),
        "",
        "## Appendix",
        "",
        _APPENDIX_POINTER,
    ]
    return "\n".join(parts)


def _render_internal(bundle: ReportBundle) -> str:
    parts = [
        _yaml_front_matter(
            bundle,
            audience=ReportAudience.INTERNAL,
            classification="IC / advisor",
        ),
        "",
        "## Advisory headline",
        "",
        _internal_headline(bundle),
        "",
        "## Context",
        "",
        (
            f"Internal month-end advisory pack for household "
            f"{bundle.household_id} as of {bundle.as_of_date.isoformat()}. "
            f"Snapshot {bundle.snapshot_id}."
        ),
        "",
        "## Exhibit A — Performance",
        "",
        _performance_table(bundle),
        "",
        "## Exhibit B — IPS drift & concentration",
        "",
        _exhibit_b_internal(bundle),
        "",
        "## Exhibit C — Tax scenarios",
        "",
        _tax_table(bundle),
        "",
        _execution_section(bundle),
        "",
        _implications_checklist(),
        "",
        _limitations_section(bundle),
        "",
        "## Appendix",
        "",
        _APPENDIX_POINTER,
        "",
        "**Data sources:**",
        "",
    ]
    parts.extend(f"- {src}" for src in bundle.data_sources)
    return "\n".join(parts) + "\n"


def render_markdown(bundle: ReportBundle, audience: ReportAudience) -> str:
    """Render audience-specific Markdown from a frozen bundle."""
    if audience == ReportAudience.EXTERNAL:
        return _render_external(bundle)
    return _render_internal(bundle)
