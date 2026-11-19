"""Unit tests for parametric safety circuit breakers."""

import unittest
from agent_treasury_stream.circuit import ParametricSafetyBreaker
from agent_treasury_stream.models import FlowConfig, SwarmRole, VolatilityTier
from agent_treasury_stream.streaming import FlowStreamEngine


class TestParametricSafetyBreaker(unittest.TestCase):
    def setUp(self):
        self.breaker = ParametricSafetyBreaker(baseline_capital=100_000.0)

    def test_nominal_state(self):
        snap = self.breaker.evaluate_valuation(100_000.0)
        self.assertEqual(snap.tier, VolatilityTier.NOMINAL)
        self.assertEqual(snap.payout_multiplier, 1.0)
        self.assertFalse(snap.emergency_lockout)

    def test_caution_tier(self):
        # 7% drawdown -> CAUTION (5% <= DD < 10%)
        snap = self.breaker.evaluate_valuation(93_000.0)
        self.assertEqual(snap.tier, VolatilityTier.CAUTION)
        self.assertEqual(snap.payout_multiplier, 0.75)

    def test_throttle_tier(self):
        # 15% drawdown -> THROTTLE (10% <= DD < 20%)
        snap = self.breaker.evaluate_valuation(85_000.0)
        self.assertEqual(snap.tier, VolatilityTier.THROTTLE)
        self.assertEqual(snap.payout_multiplier, 0.50)

    def test_defense_tier(self):
        # 25% drawdown -> DEFENSE (DD >= 20%)
        snap = self.breaker.evaluate_valuation(75_000.0)
        self.assertEqual(snap.tier, VolatilityTier.DEFENSE)
        self.assertEqual(snap.payout_multiplier, 0.0)
        self.assertTrue(snap.emergency_lockout)

    def test_exempt_daemon_immunity(self):
        engine = FlowStreamEngine()
        cfg_worker = FlowConfig("s_w", "vault", "w1", SwarmRole.GENERAL_WORKER, 1000.0, 0.0, 100.0, is_exempt=False)
        cfg_daemon = FlowConfig("s_d", "vault", "d1", SwarmRole.SAFETY_DAEMON, 1000.0, 0.0, 100.0, is_exempt=True)
        engine.register_stream(cfg_worker)
        engine.register_stream(cfg_daemon)

        # Trigger defense tier (0.0 multiplier)
        self.breaker.evaluate_valuation(70_000.0)
        self.breaker.apply_to_engine(engine, 10.0)

        # Worker throttled to 0.0, daemon remains at 1.0
        self.assertEqual(engine.registry["s_w"].throttle_rate, 0.0)
        self.assertEqual(engine.registry["s_d"].throttle_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
