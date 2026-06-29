"""CLI entry point."""

from datetime import datetime
from pathlib import Path

import click

from warehouse.dashboard.status import build_status_report
from warehouse.infra.db.seed import DEMO_HOUSEHOLD_ID


@click.group()
def main() -> None:
    """Investment Warehouse — positions-first wealth platform."""


@main.group()
def db() -> None:
    """Database migrations and seed data."""


@db.command("upgrade")
def db_upgrade() -> None:
    """Apply Alembic migrations to head."""
    from warehouse.infra.db.migrate import upgrade_head

    revision = upgrade_head()
    click.echo(f"Database at revision {revision}")


@db.command("seed")
def db_seed() -> None:
    """Seed demo household data (idempotent)."""
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.seed import seed_demo_data

    with session_scope() as session:
        created = seed_demo_data(session)
    click.echo(
        "Demo data seeded." if created else "Demo data already present."
    )


@db.command("bootstrap")
def db_bootstrap() -> None:
    """Migrate to head and seed demo data."""
    from warehouse.infra.db.bootstrap import bootstrap_database

    revision = bootstrap_database(seed=True)
    click.echo(f"Database bootstrapped at revision {revision}")


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--custodian", default="custodian_schwab", show_default=True)
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
def ingest(file: Path, custodian: str, household: str) -> None:
    """Ingest a custodian CSV file (account_id,ticker,quantity,as_of_date)."""
    from warehouse.data.ingest.runner import run_custodian_ingest
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    with session_scope() as session:
        summary = run_custodian_ingest(
            session,
            file,
            custodian_id=custodian,
            household_id=household,
        )
    click.echo(
        f"Ingest {summary.run_id}: {summary.status} "
        f"({summary.rows_processed} rows)"
    )


@main.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
def refresh(file: Path, household: str) -> None:
    """Run daily refresh workflow: ingest → reconcile → lots → corp actions."""
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database
    from warehouse.workflows.daily_refresh import run_daily_refresh

    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_daily_refresh(session, file, household_id=household)
    click.echo(f"Refresh {result.run_id}: {result.status}")
    for step in result.steps:
        click.echo(f"  {step.step_name}: {step.status} — {step.detail or ''}")


@main.command()
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
def optimize(household: str) -> None:
    """Run tax-aware optimizer and queue advisor approval."""
    from warehouse.decision.optimizer.runner import run_and_persist_optimizer
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_and_persist_optimizer(session, household)
    click.echo(f"Optimization {result.run_id}: {len(result.trades)} trades")
    click.echo(f"  Tax delta: {result.estimated_tax_delta}")
    for trade in result.trades:
        click.echo(
            f"  {trade.side} {trade.quantity} {trade.security_id} — "
            f"{trade.rationale}"
        )


@main.command()
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
@click.option("--start", "start_date", default="2024-01-01", show_default=True)
@click.option("--end", "end_date", default="2026-06-24", show_default=True)
def backtest(household: str, start_date: str, end_date: str) -> None:
    """Run walk-forward backtest and persist after-tax outcome."""
    from datetime import date

    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database
    from warehouse.research.backtest.harness import run_backtest

    bootstrap_database(seed=True)
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    with session_scope() as session:
        result = run_backtest(
            session, household, start_date=start, end_date=end
        )
    click.echo(
        f"Backtest {result.run_id}: after-tax return "
        f"{result.after_tax_return:.4f}"
    )
    click.echo(f"  Tax delta vs baseline: {result.tax_delta:.4f}")
    click.echo(f"  Config hash: {result.config_hash}")


@main.group()
def approve() -> None:
    """Advisor approval workflow."""


@approve.command("list")
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
def approve_list(household: str) -> None:
    """List pending and recent approval requests."""
    from warehouse.decision.approval.service import list_approval_requests
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    with session_scope() as session:
        requests = list_approval_requests(session, household_id=household)
    for req in requests:
        click.echo(
            f"{req.request_id} {req.status} run={req.optimization_run_id}"
        )


@approve.command("decide")
@click.argument("request_id")
@click.option("--reviewer", default="advisor:demo", show_default=True)
@click.option("--reject", is_flag=True, help="Reject instead of approve.")
def approve_decide(request_id: str, reviewer: str, reject: bool) -> None:
    """Approve or reject an optimization proposal.

    On approval, chains OMS staging (decoupled — approval records the decision;
    staging is a separate step).
    """
    from warehouse.decision.approval import ApprovalStatus
    from warehouse.decision.approval.service import update_approval_status
    from warehouse.execution.oms.service import stage_orders_from_approval
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    status = ApprovalStatus.REJECTED if reject else ApprovalStatus.APPROVED
    with session_scope() as session:
        result = update_approval_status(
            session, request_id, status=status, reviewer_id=reviewer
        )
        staged = 0
        if status == ApprovalStatus.APPROVED:
            staged = len(
                stage_orders_from_approval(
                    session, request_id, actor_id=reviewer
                )
            )
    click.echo(
        f"{result.request_id} → {result.status} by {result.reviewer_id} "
        f"({staged} orders staged)"
    )


@main.group()
def order() -> None:
    """Staged order management."""


@order.command("list")
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
def order_list(household: str) -> None:
    """List staged orders for a household."""
    from warehouse.execution.oms.service import list_staged_orders
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    with session_scope() as session:
        orders = list_staged_orders(session, household_id=household)
    for o in orders:
        click.echo(
            f"{o.order_id} {o.status} {o.side} {o.quantity} {o.security_id}"
        )


@order.command()
@click.argument("order_id")
@click.option(
    "--submit", is_flag=True, help="Mark submitted (default: filled)."
)
def order_advance(order_id: str, submit: bool) -> None:
    """Advance a staged order to submitted or filled."""
    from warehouse.execution.oms import OrderStatus
    from warehouse.execution.oms.service import update_order_status
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    status = OrderStatus.SUBMITTED if submit else OrderStatus.FILLED
    with session_scope() as session:
        result = update_order_status(session, order_id, status=status)
    click.echo(f"{result.order_id} → {result.status}")


@main.command("compare-solvers")
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
def compare_solvers(household: str) -> None:
    """Run heuristic vs MIP optimizer comparison."""
    from warehouse.decision.optimizer.compare import run_solver_comparison
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    with session_scope() as session:
        result = run_solver_comparison(session, household)
    click.echo(f"Comparison {result.comparison_id}")
    click.echo(
        f"  Heuristic: {result.heuristic_trade_count} trades, "
        f"tax {result.heuristic_tax_delta}"
    )
    click.echo(
        f"  MIP: {result.mip_trade_count} trades, tax {result.mip_tax_delta}"
    )


@main.command("tax-scenario")
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
@click.option(
    "--name", "scenario_name", default="niit_overlay", show_default=True
)
@click.option("--niit/--no-niit", default=True, show_default=True)
@click.option("--amt", is_flag=True, help="Apply AMT overlay.")
def tax_scenario(
    household: str, scenario_name: str, niit: bool, amt: bool
) -> None:
    """Run a tax scenario overlay on household unrealized gains."""
    from warehouse.decision.tax.scenarios import (
        TaxScenarioOverlays,
        run_tax_scenario,
    )
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database

    bootstrap_database(seed=True)
    overlays = TaxScenarioOverlays(apply_niit=niit, apply_amt=amt)
    with session_scope() as session:
        result = run_tax_scenario(
            session, household, scenario_name=scenario_name, overlays=overlays
        )
    click.echo(f"Scenario {result.run_id}: delta {result.tax_delta:.2f}")


@main.group()
def risk() -> None:
    """Portfolio risk evaluation (research plane)."""


@risk.command("evaluate")
@click.argument("file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--horizon",
    default="5y",
    show_default=True,
    help="Investment horizon (e.g. 5y).",
)
def risk_evaluate(file: Path, horizon: str) -> None:
    """Evaluate portfolio risk from a JSON request file."""
    import json as json_lib

    from warehouse.research.risk.api import evaluate_risk_json

    body = json_lib.loads(file.read_text())
    body["horizon"] = horizon
    status, payload = evaluate_risk_json(json_lib.dumps(body))
    if status != 200:
        click.echo(payload, err=True)
        raise SystemExit(1)
    click.echo(payload)


@main.group()
def report() -> None:
    """Household report writer."""


@report.command("write")
@click.option("--household", default=DEMO_HOUSEHOLD_ID, show_default=True)
@click.option("--as-of", "as_of", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option(
    "--period-label",
    default=None,
    help="Override period directory key.",
)
def report_write(
    household: str,
    as_of: datetime | None,
    period_label: str | None,
) -> None:
    """Build internal + external Markdown report packs for a household."""
    from warehouse.infra.db.base import session_scope
    from warehouse.infra.db.bootstrap import bootstrap_database
    from warehouse.reporting.report_writer.writer import (
        build_and_write_household_reports,
    )

    bootstrap_database(seed=True)
    as_of_date = as_of.date() if as_of is not None else None
    with session_scope() as session:
        written = build_and_write_household_reports(
            session,
            household,
            period_label=period_label,
            as_of_date=as_of_date,
            actor_id="cli:report_write",
        )
    click.echo(f"Report {written.snapshot_id}")
    click.echo(f"  Period: {written.period_label}")
    click.echo(f"  Output: {written.output_dir}")
    click.echo(f"  Internal: {written.internal_markdown_path}")
    click.echo(f"  External: {written.external_markdown_path}")
    click.echo(f"  Bundle: {written.bundle_json_path}")


@main.group()
def test() -> None:
    """Testing report generation."""


@test.command("report")
@click.option(
    "--mutation",
    is_flag=True,
    help="Run mutation testing first (slow; on-demand only).",
)
def test_report(mutation: bool) -> None:
    """Run pytest with coverage and write ``runs/testing/last_report.json``."""
    from warehouse.dashboard.mutation_report import generate_mutation_report
    from warehouse.dashboard.testing_report import generate_testing_report

    if mutation:
        generate_mutation_report()
        click.echo(
            "Mutation report written to runs/testing/mutation_report.json"
        )

    exit_code = generate_testing_report()
    if exit_code != 0:
        raise SystemExit(exit_code)
    click.echo(
        "Testing report written to runs/testing/last_report.json "
        "and runs/testing/e2e_smoke.json"
    )


@test.command("mutation")
def test_mutation() -> None:
    """Run scoped mutmut on Data + Decision; write mutation_report.json."""
    from warehouse.dashboard.mutation_report import generate_mutation_report

    path = generate_mutation_report()
    click.echo(f"Mutation report written to {path.name} in runs/testing/")


@main.command()
def info() -> None:
    """Print platform planes and build order."""
    report = build_status_report()
    click.echo(f"Investment Warehouse v{report.version}")
    click.echo("")
    click.echo(f"North star: {report.north_star}")
    click.echo(f"Build order: {report.build_order}")
    click.echo(
        f"Dashboard panels: {report.live_panel_count} live, "
        f"{report.planned_panel_count} planned"
    )
    click.echo("")
    click.echo("Run `warehouse serve` for the living status report.")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8765, show_default=True)
@click.option(
    "--risk",
    is_flag=True,
    help="Open the risk & synthetic build tracker as the landing page.",
)
def serve(host: str, port: int, risk: bool) -> None:
    """Start the living status dashboard."""
    from warehouse.dashboard.server import serve as run_dashboard

    run_dashboard(host=host, port=port, risk=risk)
