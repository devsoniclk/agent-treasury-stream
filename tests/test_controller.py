"""Unit tests for master controller, simulator, CLI and MCP server."""

import unittest
from click.testing import CliRunner

from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.simulation import SwarmTreasurySimulator
from agent_treasury_stream.cli import cli
from agent_treasury_stream.mcp_server import (
    tool_create_stream,
    tool_get_stream_status,
    tool_mint_compute_quota,
    tool_check_portfolio_drift,
)
from agent_treasury_stream.models import FlowCurveType, SwarmRole


class TestControllerAndEcosystem(unittest.TestCase):
    def test_controller_open_stream_and_sync(self):
        ctrl = AutonomousTreasuryController()
        snap = ctrl.open_stream(
            stream_id="test_s",
            beneficiary="agent_x",
            role=SwarmRole.SENTINEL,
            total_allocation=5000.0,
            start_epoch=0.0,
            end_epoch=1000.0,
        )
        self.assertEqual(snap.config.stream_id, "test_s")
        val, tier, dd = ctrl.sync_treasury_state(100.0)
        self.assertGreater(val, 0.0)

    def test_controller_insolvency_guard(self):
        ctrl = AutonomousTreasuryController()
        with self.assertRaises(ValueError):
            ctrl.open_stream(
                stream_id="insolvent_s",
                beneficiary="agent_y",
                role=SwarmRole.SENTINEL,
                total_allocation=10_000_000.0,  # Far exceeds free USDC
                start_epoch=0.0,
                end_epoch=1000.0,
            )

    def test_swarm_simulation_runs(self):
        sim = SwarmTreasurySimulator(simulation_days=1)
        res = sim.run_simulation()
        self.assertIn("final_portfolio_valuation_usd", res)
        self.assertGreater(res["final_portfolio_valuation_usd"], 0.0)

    def test_cli_curve_price(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["curve-price", "--supply", "100.0"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Spot Unit Price", result.output)

    def test_cli_portfolio_drift(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["portfolio-drift"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Holdings & Drift", result.output)

    def test_mcp_tools(self):
        res1 = tool_create_stream("mcp_s1", "mcp_agent", "SENTINEL", 1000.0)
        self.assertIn("success", res1)

        res2 = tool_get_stream_status("mcp_s1", 86400.0)
        self.assertIn("vested_usd", res2)

        res3 = tool_mint_compute_quota("mcp_agent", 50.0)
        self.assertIn("success", res3)

        res4 = tool_check_portfolio_drift()
        self.assertIn("total_value_usd", res4)


if __name__ == "__main__":
    unittest.main()
