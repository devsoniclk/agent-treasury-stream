"""Unit tests for agent-treasury-stream CLI commands."""

from click.testing import CliRunner
from agent_treasury_stream.cli import cli, main


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Agent Treasury Stream" in result.output
    assert "simulate" in result.output
    assert "curve-price" in result.output
    assert "portfolio-drift" in result.output


def test_cli_curve_price() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["curve-price", "--supply", "100", "--congestion", "1.2"])
    assert result.exit_code == 0
    assert "Spot Unit Price" in result.output


def test_cli_portfolio_drift() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["portfolio-drift"])
    assert result.exit_code == 0
    assert "Treasury Holdings & Drift Analysis" in result.output
    assert "USDC" in result.output
    assert "ETH" in result.output


def test_cli_simulate() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["simulate", "--days", "3"])
    assert result.exit_code == 0
    assert "Simulation Summary" in result.output


def test_cli_main_entrypoint(monkeypatch) -> None:
    # Test main() invocation
    import sys
    monkeypatch.setattr(sys, "argv", ["agent-treasury-stream", "--help"])
    try:
        main()
    except SystemExit as e:
        assert e.code == 0
