"""Unit tests for TreasuryRebalancer drift monitoring and hedging."""

import pytest
from agent_treasury_stream.models import ReserveHolding
from agent_treasury_stream.rebalance import TreasuryRebalancer


@pytest.fixture
def rebalancer() -> TreasuryRebalancer:
    holdings = {
        "USDC": ReserveHolding(ticker="USDC", units=500_000.0, unit_price_usd=1.0, target_weight=0.50),
        "ETH": ReserveHolding(ticker="ETH", units=80.0, unit_price_usd=2500.0, target_weight=0.20),
        "SOL": ReserveHolding(ticker="SOL", units=1000.0, unit_price_usd=150.0, target_weight=0.15),
        "HLP": ReserveHolding(ticker="HLP", units=150_000.0, unit_price_usd=1.0, target_weight=0.15),
    }
    return TreasuryRebalancer(holdings=holdings, drift_band_pct=0.05, execution_buffer_pct=0.0005)


def test_initial_portfolio_valuation_and_weights(rebalancer: TreasuryRebalancer) -> None:
    # 500k + 200k + 150k + 150k = 1,000,000 USD
    assert rebalancer.get_portfolio_usd_value() == 1_000_000.0
    drifts = rebalancer.compute_drift_deltas()
    for drift in drifts.values():
        assert pytest.approx(drift, abs=1e-6) == 0.0


def test_price_refresh_and_drift_detection(rebalancer: TreasuryRebalancer) -> None:
    # ETH surges from 2,500 to 5,000 (+100%)
    rebalancer.refresh_price("ETH", 5000.0)
    # ETH is now 80 * 5000 = 400,000 USD
    # Total portfolio is 500k + 400k + 150k + 150k = 1,200,000 USD
    # Target ETH weight is 20% -> 240,000 USD
    # Current ETH weight is 400k / 1.2M = 33.33% -> drift = 13.33% >= 5%
    needs_rebal, dominant, max_drift = rebalancer.inspect_rebalance_triggers()
    assert needs_rebal
    assert dominant == "ETH"
    assert pytest.approx(max_drift, abs=1e-3) == 0.1333


def test_price_refresh_invalid_ticker(rebalancer: TreasuryRebalancer) -> None:
    with pytest.raises(KeyError, match="Holding 'UNKNOWN' not found"):
        rebalancer.refresh_price("UNKNOWN", 100.0)
    with pytest.raises(ValueError, match="Price must be strictly positive"):
        rebalancer.refresh_price("ETH", -10.0)


def test_plan_rebalance_orders_with_execution_buffer(rebalancer: TreasuryRebalancer) -> None:
    # ETH surges to 4,000
    rebalancer.refresh_price("ETH", 4000.0)
    orders = rebalancer.plan_rebalance_orders(current_epoch=100.0)
    assert len(orders) > 0

    # ETH should have a SELL directive with 0.05% discount execution buffer
    eth_orders = [o for o in orders if o.instrument == "ETH" and o.direction == "SELL"]
    assert len(eth_orders) == 1
    eth_order = eth_orders[0]
    expected_entry = 4000.0 * (1.0 - 0.0005)
    assert pytest.approx(eth_order.target_entry) == expected_entry
    assert eth_order.expected_rr == 2.0


def test_plan_rebalance_collar_hedges(rebalancer: TreasuryRebalancer) -> None:
    orders = rebalancer.plan_rebalance_orders(current_epoch=100.0, overlay_collar_hedges=True)
    perp_hedges = [o for o in orders if "-PERP" in o.instrument]
    assert len(perp_hedges) == 2  # ETH-PERP and SOL-PERP
    for hedge in perp_hedges:
        assert hedge.direction == "HEDGE_SHORT"
        assert hedge.leverage == 1.0


def test_record_execution(rebalancer: TreasuryRebalancer) -> None:
    # Record a SELL signal on ETH
    initial_eth = rebalancer.holdings["ETH"].units
    initial_usdc = rebalancer.holdings["USDC"].units

    rebalancer.refresh_price("ETH", 4000.0)
    orders = rebalancer.plan_rebalance_orders(current_epoch=100.0)
    eth_sell = next(o for o in orders if o.instrument == "ETH" and o.direction == "SELL")

    rebalancer.record_execution(eth_sell)
    assert rebalancer.holdings["ETH"].units < initial_eth
    assert rebalancer.holdings["USDC"].units > initial_usdc
    assert len(rebalancer.signal_ledger) == 1
