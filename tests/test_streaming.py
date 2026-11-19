"""Unit tests for the continuous streaming engine."""

import unittest
from agent_treasury_stream.models import (
    FlowConfig,
    FlowCurveType,
    StreamLifecycleState,
    SwarmRole,
)
from agent_treasury_stream.streaming import FlowStreamEngine


class TestFlowStreamEngine(unittest.TestCase):
    def setUp(self):
        self.engine = FlowStreamEngine()
        self.config_linear = FlowConfig(
            stream_id="s_linear",
            funder="vault",
            beneficiary="agent_a",
            role=SwarmRole.SENTINEL,
            total_allocation=1000.0,
            start_epoch=0.0,
            end_epoch=100.0,
            curve_type=FlowCurveType.LINEAR,
        )

    def test_register_and_vest_linear(self):
        self.engine.register_stream(self.config_linear)
        # At t=0, vested is 0
        self.assertAlmostEqual(self.engine.get_vested_balance("s_linear", 0.0), 0.0)
        # At t=50, vested is 500
        self.assertAlmostEqual(self.engine.get_vested_balance("s_linear", 50.0), 500.0)
        # At t=100, vested is 1000
        self.assertAlmostEqual(self.engine.get_vested_balance("s_linear", 100.0), 1000.0)
        # At t=150, capped at 1000
        self.assertAlmostEqual(self.engine.get_vested_balance("s_linear", 150.0), 1000.0)

    def test_withdrawal(self):
        self.engine.register_stream(self.config_linear)
        # At t=50, claimable is 500
        self.assertAlmostEqual(self.engine.get_claimable_amount("s_linear", 50.0), 500.0)
        paid = self.engine.execute_withdrawal("s_linear", 200.0, 50.0)
        self.assertAlmostEqual(paid, 200.0)
        self.assertAlmostEqual(self.engine.get_claimable_amount("s_linear", 50.0), 300.0)

    def test_withdrawal_exceeds(self):
        self.engine.register_stream(self.config_linear)
        with self.assertRaises(ValueError):
            self.engine.execute_withdrawal("s_linear", 100.0, 0.0)

    def test_cliff_vesting(self):
        cfg_cliff = FlowConfig(
            stream_id="s_cliff",
            funder="vault",
            beneficiary="agent_b",
            role=SwarmRole.RESEARCH_AGENT,
            total_allocation=1000.0,
            start_epoch=0.0,
            end_epoch=100.0,
            curve_type=FlowCurveType.CLIFF,
            cliff_epoch=20.0,
            cliff_amount=200.0,
        )
        self.engine.register_stream(cfg_cliff)
        # Before cliff (t=10), vested is 0
        self.assertAlmostEqual(self.engine.get_vested_balance("s_cliff", 10.0), 0.0)
        # At cliff (t=20), cliff releases 200
        self.assertGreaterEqual(self.engine.get_vested_balance("s_cliff", 20.0), 200.0)

    def test_exponential_vesting(self):
        cfg_exp = FlowConfig(
            stream_id="s_exp",
            funder="vault",
            beneficiary="agent_c",
            role=SwarmRole.EXECUTION_AGENT,
            total_allocation=1000.0,
            start_epoch=0.0,
            end_epoch=100.0,
            curve_type=FlowCurveType.EXPONENTIAL,
            exponent=2.0,
        )
        self.engine.register_stream(cfg_exp)
        # At t=50 (50% progress), progress^2 = 0.25 -> 250
        self.assertAlmostEqual(self.engine.get_vested_balance("s_exp", 50.0), 250.0)

    def test_pause_and_resume(self):
        self.engine.register_stream(self.config_linear)
        self.engine.get_vested_balance("s_linear", 20.0)
        self.engine.pause_flow("s_linear", 20.0)
        self.assertEqual(self.engine.registry["s_linear"].status, StreamLifecycleState.PAUSED)
        # While paused, vested does not increase
        self.assertAlmostEqual(self.engine.get_vested_balance("s_linear", 40.0), 200.0)
        self.engine.resume_flow("s_linear", 40.0)
        self.assertEqual(self.engine.registry["s_linear"].status, StreamLifecycleState.ACTIVE)

    def test_terminate_and_settle(self):
        self.engine.register_stream(self.config_linear)
        # At t=40, vested is 400. Terminate should return 400 claim and 600 refund
        claim, refund = self.engine.terminate_and_settle("s_linear", 40.0)
        self.assertAlmostEqual(claim, 400.0)
        self.assertAlmostEqual(refund, 600.0)
        self.assertAlmostEqual(claim + refund, 1000.0)  # Conservation invariant

    def test_throttle_scaling(self):
        self.engine.register_stream(self.config_linear)
        self.engine.set_throttle("s_linear", 0.50, 0.0)
        # At 50% throttle, t=50 should vest 250 instead of 500
        self.assertAlmostEqual(self.engine.get_vested_balance("s_linear", 50.0), 250.0)

    def test_solvency_runway(self):
        self.engine.register_stream(self.config_linear)
        is_solvent, req, ratio = self.engine.check_solvency_runway(
            liquid_reserves_usd=1000.0,
            horizon_seconds=10.0,
            current_epoch=50.0,
        )
        self.assertTrue(is_solvent)
        self.assertAlmostEqual(req, 100.0)  # 10 USD/s * 10s


if __name__ == "__main__":
    unittest.main()
