"""Unit tests for compute bonding curve engine."""

import unittest
from agent_treasury_stream.bonding import ComputeBondingEngine
from agent_treasury_stream.models import BondingCurveParams


class TestComputeBondingEngine(unittest.TestCase):
    def setUp(self):
        self.params = BondingCurveParams(
            base_unit_price=1.0,
            sensitivity_alpha=0.005,
            exponent_k=2.0,
            nominal_fee_burn_pct=0.05,
        )
        self.engine = ComputeBondingEngine(self.params)

    def test_spot_price_increases_with_supply(self):
        p0 = self.engine.get_spot_unit_price(0.0)
        p10 = self.engine.get_spot_unit_price(10.0)
        self.assertAlmostEqual(p0, 1.0)
        self.assertGreater(p10, p0)

    def test_congestion_multiplier(self):
        p_normal = self.engine.get_spot_unit_price(10.0, congestion_index=1.0)
        p_congested = self.engine.get_spot_unit_price(10.0, congestion_index=2.0)
        self.assertAlmostEqual(p_congested, p_normal * 2.0)

    def test_mint_quota(self):
        units, fee_burned, avg_price = self.engine.mint_quota(
            agent_id="agent_1",
            gross_deposit_usd=100.0,
        )
        self.assertGreater(units, 0.0)
        self.assertAlmostEqual(fee_burned, 5.0)  # 5% base fee burn
        self.assertGreaterEqual(self.engine.circulating_supply, units)
        self.assertAlmostEqual(self.engine.treasury_vault_usd, 95.0)

    def test_consume_compute(self):
        units, _, _ = self.engine.mint_quota(agent_id="agent_1", gross_deposit_usd=100.0)
        initial_supply = self.engine.circulating_supply
        cycles = self.engine.consume_compute(agent_id="agent_1", units_to_burn=units * 0.5)
        self.assertGreater(cycles, 0.0)
        self.assertLess(self.engine.circulating_supply, initial_supply)

    def test_consume_excess_fails(self):
        self.engine.mint_quota(agent_id="agent_1", gross_deposit_usd=50.0)
        with self.assertRaises(ValueError):
            self.engine.consume_compute(agent_id="agent_1", units_to_burn=1000.0)

    def test_liquidate_quota(self):
        units, _, _ = self.engine.mint_quota(agent_id="agent_1", gross_deposit_usd=100.0)
        refund, fee = self.engine.liquidate_surplus_quota(agent_id="agent_1", units_to_redeem=units * 0.5)
        self.assertGreater(refund, 0.0)
        self.assertGreater(fee, 0.0)


if __name__ == "__main__":
    unittest.main()
