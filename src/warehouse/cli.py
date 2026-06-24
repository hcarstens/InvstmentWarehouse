"""CLI entry point."""

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
    click.echo("Demo data seeded." if created else "Demo data already present.")


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
    click.echo(f"Ingest {summary.run_id}: {summary.status} ({summary.rows_processed} rows)")


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
def serve(host: str, port: int) -> None:
    """Start the living status dashboard."""
    from warehouse.dashboard.server import serve as run_dashboard

    run_dashboard(host=host, port=port)
