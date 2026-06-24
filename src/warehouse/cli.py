"""CLI entry point."""

import click

from warehouse.dashboard.status import build_status_report


@click.group()
def main() -> None:
    """Investment Warehouse — positions-first wealth platform."""


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
