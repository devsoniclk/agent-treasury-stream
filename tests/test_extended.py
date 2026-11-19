"""Extended test suite testing CLI, MCP server error handling, and edge cases."""

import json
import unittest
from click.testing import CliRunner

from agent_treasury_stream.cli import cli
from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.mcp_server import (
    tool_create_stream,
    tool_get_stream_status,
    tool_mint_compute_quota,
    tool_check_portfolio_drift,
)
from agent_treasury_stream.models import FlowCurveType, SwarmRole


class TestExtendedCoverage(unittest.TestCase):
    def test_cli_simulate(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["simulate", "--days", "1"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Simulation Summary", result.output)

    def test_mcp_invalid_role(self):
        res = tool_create_stream("s_bad", "b", "INVALID_ROLE", 100.0)
        data = json.loads(res)
        self.assertIn("error", data)

    def test_mcp_invalid_curve(self):
        res = tool_create_stream("s_bad", "b", "SENTINEL", 100.0, curve_type="INVALID_CURVE")
        data = json.loads(res)
        self.assertIn("error", data)

    def test_mcp_missing_stream(self):
        res = tool_get_stream_status("nonexistent_stream")
        data = json.loads(res)
        self.assertIn("error", data)

    def test_mcp_negative_mint(self):
        res = tool_mint_compute_quota("agent_neg", -50.0)
        data = json.loads(res)
        self.assertIn("error", data)

    def test_controller_top_up_and_rebalance(self):
        ctrl = AutonomousTreasuryController()
        # Open stream
        snap = ctrl.open_stream("topup_s", "agent_z", SwarmRole.SENTINEL, 1000.0, 0.0, 100.0)
        self.assertEqual(snap.status.value, "ACTIVE")
        # Trigger rebalance
        ctrl.rebalancer.refresh_price("ETH", 1000.0)
        orders = ctrl.rebalancer.plan_rebalance_orders(10.0)
        self.assertTrue(len(orders) > 0)
        # Execute an order
        ctrl.rebalancer.record_execution(orders[0])
        self.assertTrue(len(ctrl.rebalancer.signal_ledger) > 0)

    def test_bonding_curve_slippage_protection(self):
        ctrl = AutonomousTreasuryController()
        with self.assertRaises(ValueError):
            # Request impossible 0% slippage on large mint
            ctrl.bonding_engine.mint_quota("agent_slip", 10_000.0, slippage_cap_pct=0.000001)

    def test_circuit_breaker_reset(self):
        ctrl = AutonomousTreasuryController()
        ctrl.safety_breaker.evaluate_valuation(50_000.0)
        self.assertGreater(ctrl.safety_breaker.snapshot.active_drawdown_pct, 0.0)
        ctrl.safety_breaker.reset_peak(100_000.0)
        self.assertEqual(ctrl.safety_breaker.snapshot.active_drawdown_pct, 0.0)

    def test_streaming_velocity_and_unvested(self):
        ctrl = AutonomousTreasuryController()
        ctrl.open_stream("vel_s", "agent_v", SwarmRole.SENTINEL, 10_000.0, 0.0, 100.0)
        vel = ctrl.stream_engine.get_instantaneous_velocity("vel_s", 50.0)
        self.assertAlmostEqual(vel, 100.0)  # 10k / 100s
        liabilities = ctrl.stream_engine.calculate_total_outstanding_liabilities(50.0)
        self.assertAlmostEqual(liabilities, 5000.0)

    def test_rebalance_price_validation(self):
        ctrl = AutonomousTreasuryController()
        with self.assertRaises(ValueError):
            ctrl.rebalancer.refresh_price("ETH", -100.0)
        with self.assertRaises(KeyError):
            ctrl.rebalancer.refresh_price("NONEXISTENT", 100.0)

    def test_bonding_estimate_cost_and_burn_tracking(self):
        ctrl = AutonomousTreasuryController()
        cost = ctrl.bonding_engine.estimate_mint_cost(10.0)
        self.assertGreater(cost, 0.0)
        units, burned_usd, _ = ctrl.mint_compute_quota("burn_agent", 500.0)
        self.assertGreater(burned_usd, 0.0)
        cycles = ctrl.bonding_engine.consume_compute("burn_agent", units * 0.5)
        self.assertGreater(cycles, 0.0)
        self.assertGreater(ctrl.bonding_engine.cumulative_tokens_burned, 0.0)

    def test_streaming_pause_velocity(self):
        ctrl = AutonomousTreasuryController()
        ctrl.open_stream("pause_vel_s", "agent_pv", SwarmRole.SENTINEL, 10_000.0, 0.0, 100.0)
        ctrl.stream_engine.pause_flow("pause_vel_s", 20.0)
        # Paused stream should have 0 instantaneous velocity
        vel = ctrl.stream_engine.get_instantaneous_velocity("pause_vel_s", 30.0)
        self.assertEqual(vel, 0.0)

    def test_circuit_breaker_stress_escalation(self):
        ctrl = AutonomousTreasuryController()
        snap_normal = ctrl.safety_breaker.evaluate_valuation(90_000.0, liquidity_stress_factor=0.0)
        snap_stressed = ctrl.safety_breaker.evaluate_valuation(90_000.0, liquidity_stress_factor=1.0)
        self.assertGreater(snap_stressed.burn_fee_rate, snap_normal.burn_fee_rate)


if __name__ == "__main__":
    unittest.main()
