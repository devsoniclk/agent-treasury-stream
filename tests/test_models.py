"""Unit tests for models and data structures."""

import unittest
from agent_treasury_stream.models import (
    FlowConfig,
    FlowCurveType,
    HedgingSignal,
    ReserveHolding,
    SwarmRole,
    VolatilityTier,
)


class TestModels(unittest.TestCase):
    def test_flow_config_valid(self):
        cfg = FlowConfig(
            stream_id="s1",
            funder="treasury",
            beneficiary="agent1",
            role=SwarmRole.SENTINEL,
            total_allocation=1000.0,
            start_epoch=0.0,
            end_epoch=100.0,
        )
        self.assertEqual(cfg.stream_id, "s1")
        self.assertEqual(cfg.curve_type, FlowCurveType.LINEAR)

    def test_flow_config_invalid_epochs(self):
        with self.assertRaises(ValueError):
            FlowConfig(
                stream_id="s1",
                funder="treasury",
                beneficiary="agent1",
                role=SwarmRole.SENTINEL,
                total_allocation=1000.0,
                start_epoch=100.0,
                end_epoch=50.0,
            )

    def test_flow_config_negative_allocation(self):
        with self.assertRaises(ValueError):
            FlowConfig(
                stream_id="s1",
                funder="treasury",
                beneficiary="agent1",
                role=SwarmRole.SENTINEL,
                total_allocation=-10.0,
                start_epoch=0.0,
                end_epoch=100.0,
            )

    def test_flow_config_invalid_cliff(self):
        with self.assertRaises(ValueError):
            FlowConfig(
                stream_id="s1",
                funder="treasury",
                beneficiary="agent1",
                role=SwarmRole.SENTINEL,
                total_allocation=1000.0,
                start_epoch=0.0,
                end_epoch=100.0,
                cliff_amount=1500.0,
            )

    def test_reserve_holding(self):
        h = ReserveHolding(ticker="ETH", units=10.0, unit_price_usd=2000.0, target_weight=0.2)
        self.assertEqual(h.total_usd_value, 20000.0)

    def test_hedging_signal_format(self):
        sig = HedgingSignal(
            instrument="ETH-PERP",
            direction="HEDGE_SHORT",
            target_entry=2500.0,
            stop_boundary=2600.0,
            profit_boundary=2300.0,
            leverage=1.0,
            expected_rr=2.0,
            allocation_size=10.0,
            epoch=100.0,
            memo="Test hedge",
        )
        directive = sig.format_pipeline_directive()
        self.assertIn("ETH-PERP", directive)
        self.assertIn("HEDGE_SHORT", directive)
        self.assertIn("1.0x", directive)


if __name__ == "__main__":
    unittest.main()
