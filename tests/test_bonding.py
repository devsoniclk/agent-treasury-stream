"""Unit tests for ComputeBondingEngine polynomial bonding curve."""

import pytest
from agent_treasury_stream.bonding import ComputeBondingEngine
from agent_treasury_stream.models import BondingCurveParams


@pytest.fixture
def bonding_engine() -> ComputeBondingEngine:
    params = BondingCurveParams(
        base_unit_price=1.0,
        sensitivity_alpha=0.01,
        exponent_k=2.0,
        nominal_fee_burn_pct=0.05,
        max_quota_supply=10_000.0,
    )
    return ComputeBondingEngine(params=params)


def test_spot_unit_price(bonding_engine: ComputeBondingEngine) -> None:
    # At supply 0: P0 = 1.0
    assert bonding_engine.get_spot_unit_price(0.0) == 1.0

    # At supply 10: P(10) = 1.0 + 0.01 * (10^2) = 1.0 + 1.0 = 2.0
    assert pytest.approx(bonding_engine.get_spot_unit_price(10.0)) == 2.0

    # With congestion multiplier 2.0
    assert pytest.approx(bonding_engine.get_spot_unit_price(10.0, congestion_index=2.0)) == 4.0


def test_reserve_integral(bonding_engine: ComputeBondingEngine) -> None:
    # R(s) = P0 * s + (alpha / (k + 1)) * s^(k + 1)
    # R(10) = 1.0 * 10 + (0.01 / 3) * 1000 = 10 + 3.33333 = 13.33333
    expected = 10.0 + (0.01 / 3.0) * 1000.0
    assert pytest.approx(bonding_engine.calculate_reserve_integral(10.0)) == expected


def test_estimate_mint_cost(bonding_engine: ComputeBondingEngine) -> None:
    # Cost to mint first 10 units: R(10) - R(0) = R(10)
    cost = bonding_engine.estimate_mint_cost(10.0)
    expected = 10.0 + (0.01 / 3.0) * 1000.0
    assert pytest.approx(cost) == expected
    assert bonding_engine.estimate_mint_cost(-5.0) == 0.0


def test_solve_units_for_deposit(bonding_engine: ComputeBondingEngine) -> None:
    # If deposit is R(10), solved units should be approx 10.0
    deposit = 10.0 + (0.01 / 3.0) * 1000.0
    units = bonding_engine.solve_units_for_deposit(deposit)
    assert pytest.approx(units, abs=1e-5) == 10.0
    assert bonding_engine.solve_units_for_deposit(0.0) == 0.0


def test_mint_quota_success(bonding_engine: ComputeBondingEngine) -> None:
    agent_id = "agent-alpha"
    deposit = 100.0

    units, fee_burned, avg_price = bonding_engine.mint_quota(
        agent_id=agent_id, gross_deposit_usd=deposit
    )

    # 5% fee burned
    assert fee_burned == 5.0
    net_deposit = 95.0

    assert units > 0.0
    assert pytest.approx(avg_price) == net_deposit / units
    assert bonding_engine.circulating_supply == units
    assert bonding_engine.treasury_vault_usd == net_deposit
    assert bonding_engine.cumulative_fee_burned_usd == 5.0

    # Allocation record created
    rec = bonding_engine.allocations[agent_id]
    assert rec.units_minted == units
    assert rec.reserve_spent_usd == deposit


def test_mint_quota_invalid_deposit(bonding_engine: ComputeBondingEngine) -> None:
    with pytest.raises(ValueError, match="Gross deposit must be positive"):
        bonding_engine.mint_quota("agent-1", gross_deposit_usd=-50.0)


def test_mint_quota_slippage_cap(bonding_engine: ComputeBondingEngine) -> None:
    # Attempt huge mint with 1% slippage cap
    with pytest.raises(ValueError, match="Slippage limit violated"):
        bonding_engine.mint_quota(
            agent_id="agent-whale",
            gross_deposit_usd=10_000.0,
            slippage_cap_pct=0.01,
        )


def test_mint_quota_supply_cap(bonding_engine: ComputeBondingEngine) -> None:
    # Set tight quota supply cap
    bonding_engine.params.max_quota_supply = 50.0
    with pytest.raises(ValueError, match="Minting would exceed max supply"):
        bonding_engine.mint_quota(
            agent_id="agent-whale",
            gross_deposit_usd=100_000.0,
        )


def test_consume_compute(bonding_engine: ComputeBondingEngine) -> None:
    agent_id = "agent-compute"
    units, _, _ = bonding_engine.mint_quota(agent_id, gross_deposit_usd=100.0)

    delivered = bonding_engine.consume_compute(
        agent_id=agent_id,
        units_to_burn=units * 0.5,
        cycles_per_unit=2.0,
    )
    assert pytest.approx(delivered) == (units * 0.5) * 2.0
    assert bonding_engine.cumulative_tokens_burned == units * 0.5

    # Consuming more than available fails
    with pytest.raises(ValueError, match="Insufficient compute quota"):
        bonding_engine.consume_compute(agent_id, units * 0.8)


def test_liquidate_surplus_quota(bonding_engine: ComputeBondingEngine) -> None:
    agent_id = "agent-exit"
    units, _, _ = bonding_engine.mint_quota(agent_id, gross_deposit_usd=100.0)

    refund, exit_fee = bonding_engine.liquidate_surplus_quota(agent_id, units_to_redeem=units * 0.5)
    assert refund > 0.0
    assert exit_fee > 0.0

    # Over-redeem fails
    with pytest.raises(ValueError, match="Insufficient surplus quota"):
        bonding_engine.liquidate_surplus_quota(agent_id, units_to_redeem=units)
