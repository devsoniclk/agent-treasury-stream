"""Unit tests for portfolio rebalancing and execution buffer."""

import unittest
from agent_treasury_stream.rebalance import TreasuryRebalancer


class TestTreasuryRebalancer(unittest.TestCase):
    def setUp(self):
        self.rebalancer = TreasuryRebalancer(drift_band_pct=0.05, execution_buffer_pct=0.0005)
        self.rebalancer.set_holding("USDC", 50_000.0, 1.0, 0.50)
        self.rebalancer.set_holding("ETH", 20.0, 2500.0, 0.50)  # 50k ETH, total 100k

    def test_initial_zero_drift(self):
        drifts = self.rebalancer.compute_drift_deltas()
        self.assertAlmostEqual(drifts["USDC"], 0.0)
        self.assertAlmostEqual(drifts["ETH"], 0.0)
        trigger, _, _ = self.rebalancer.inspect_rebalance_triggers()
        self.assertFalse(trigger)

    def test_drift_trigger_on_price_shift(self):
        # ETH doubles to $5000 -> ETH value is 100k, USDC is 50k, total 150k
        # ETH weight = 100/150 = 66.7% (drift 16.7%)
        self.rebalancer.refresh_price("ETH", 5000.0)
        trigger, dominant, max_drift = self.rebalancer.inspect_rebalance_triggers()
        self.assertTrue(trigger)
        self.assertIn(dominant, ("ETH", "USDC"))
        self.assertGreater(max_drift, 0.05)

    def test_rebalance_order_generation(self):
        self.rebalancer.refresh_price("ETH", 5000.0)
        directives = self.rebalancer.plan_rebalance_orders(100.0)
        self.assertTrue(len(directives) > 0)
        eth_order = next(d for d in directives if d.instrument == "ETH")
        self.assertEqual(eth_order.direction, "SELL")
        # Check execution buffer (sell bids slightly below spot)
        self.assertLess(eth_order.target_entry, 5000.0)

    def test_delta_neutral_collar_hedging(self):
        directives = self.rebalancer.plan_rebalance_orders(100.0, overlay_collar_hedges=True)
        perp_order = next((d for d in directives if "PERP" in d.instrument), None)
        self.assertIsNotNone(perp_order)
        self.assertEqual(perp_order.direction, "HEDGE_SHORT")


if __name__ == "__main__":
    unittest.main()
