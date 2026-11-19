"""Command-line interface for agent-treasury-stream."""

from __future__ import annotations

import sys
import json
import click
from rich.console import Console
from rich.table import Table

from agent_treasury_stream.models import (
    FlowCurveType,
    SwarmRole,
)
from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.simulation import SwarmTreasurySimulator

console = Console()


@click.group()
def cli() -> None:
    """Agent Treasury Stream: Autonomous continuous micro-streaming & bonding curves."""
    pass


@cli.command("simulate")
@click.option("--days", default=30, help="Simulation duration in days.")
def simulate_cmd(days: int) -> None:
    """Run a 30-day multi-agent swarm treasury simulation."""
    console.print(f"[bold cyan]Running {days}-day autonomous swarm simulation...[/bold cyan]")
    sim = SwarmTreasurySimulator(simulation_days=days)
    results = sim.run_simulation()

    table = Table(title="Simulation Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    for k, v in results.items():
        if isinstance(v, float):
            table.add_row(k, f"{v:,.2f}" if "usd" in k or "supply" in k else f"{v*100:.2f}%")
        else:
            table.add_row(k, str(v))

    console.print(table)


@cli.command("curve-price")
@click.option("--supply", default=0.0, help="Circulating compute unit supply.")
@click.option("--congestion", default=1.0, help="Demand congestion multiplier.")
def curve_price_cmd(supply: float, congestion: float) -> None:
    """Calculate instantaneous spot price for compute quota."""
    ctrl = AutonomousTreasuryController()
    price = ctrl.bonding_engine.get_spot_unit_price(supply=supply, congestion_index=congestion)
    console.print(f"[bold green]Spot Unit Price:[/bold green] ${price:.4f} USD (Supply: {supply:,.1f}, Congestion: {congestion:.2f}x)")


@cli.command("portfolio-drift")
def portfolio_drift_cmd() -> None:
    """Inspect treasury reserve allocation and weight drift."""
    ctrl = AutonomousTreasuryController()
    drifts = ctrl.rebalancer.compute_drift_deltas()

    table = Table(title="Treasury Holdings & Drift Analysis")
    table.add_column("Ticker", style="cyan")
    table.add_column("Units", style="magenta")
    table.add_column("Price (USD)", style="white")
    table.add_column("Value (USD)", style="green")
    table.add_column("Target %", style="yellow")
    table.add_column("Current %", style="blue")
    table.add_column("Drift %", style="red")

    for ticker, h in ctrl.rebalancer.holdings.items():
        table.add_row(
            ticker,
            f"{h.units:,.2f}",
            f"${h.unit_price_usd:,.2f}",
            f"${h.total_usd_value:,.2f}",
            f"{h.target_weight * 100:.1f}%",
            f"{h.current_weight * 100:.1f}%",
            f"{drifts.get(ticker, 0.0) * 100:.2f}%",
        )

    console.print(table)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
