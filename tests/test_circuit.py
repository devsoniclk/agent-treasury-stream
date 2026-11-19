"""Unit tests for ParametricSafetyBreaker drawdown circuit breakers."""

import pytest
from agent_treasury_stream.circuit import ParametricSafetyBreaker
from agent_treasury_stream.models import (
    FlowConfig,
    SwarmRole,
    VolatilityTier,
)
from agent_treasury_stream.streaming import FlowStreamEngine


@pytest.fixture
def safety_breaker() -> ParametricSafetyBreaker:
    return ParametricSafetyBreaker(
        baseline_capital=1_000_000.0,
        caution_tier_pct=0.05,
        throttle_tier_pct=0.10,
        defense_tier_pct=0.20,
        nominal_burn_fee=0.05,
    )


def test_baseline_capital_validation() -> None:
    with pytest.raises(ValueError, match="Baseline capital must be positive"):
        ParametricSafetyBreaker(baseline_capital=-100.0)


def test_drawdown_tiers(safety_breaker: ParametricSafetyBreaker) -> None:
    # 1. Normal regime (Drawdown 2% < 5%)
    snap = safety_breaker.evaluate_valuation(980_000.0)
    assert snap.tier == VolatilityTier.NOMINAL
    assert snap.payout_multiplier == 1.00
    assert snap.burn_fee_rate == 0.05
    assert not snap.emergency_lockout

    # 2. Caution regime (Drawdown 7% >= 5% and < 10%)
    snap = safety_breaker.evaluate_valuation(930_000.0)
    assert snap.tier == VolatilityTier.CAUTION
    assert snap.payout_multiplier == 0.75
    assert snap.burn_fee_rate == 0.10
    assert not snap.emergency_lockout

    # 3. Throttle regime (Drawdown 15% >= 10% and < 20%)
    snap = safety_breaker.evaluate_valuation(850_000.0)
    assert snap.tier == VolatilityTier.THROTTLE
    assert snap.payout_multiplier == 0.50
    assert snap.burn_fee_rate == 0.20
    assert not snap.emergency_lockout

    # 4. Defense regime (Drawdown 25% >= 20%)
    snap = safety_breaker.evaluate_valuation(750_000.0)
    assert snap.tier == VolatilityTier.DEFENSE
    assert snap.payout_multiplier == 0.00
    assert snap.burn_fee_rate == 0.35
    assert snap.emergency_lockout


def test_high_water_mark_ratchet(safety_breaker: ParametricSafetyBreaker) -> None:
    # Capital increases to 1.2M -> new HWM
    snap = safety_breaker.evaluate_valuation(1_200_000.0)
    assert safety_breaker.peak_capital == 1_200_000.0
    assert snap.peak_valuation == 1_200_000.0
    assert snap.active_drawdown_pct == 0.0

    # Drawdown is now measured against 1.2M
    # At 1.08M, drawdown is (1.2 - 1.08) / 1.2 = 0.12 / 1.2 = 10% -> THROTTLE
    snap = safety_breaker.evaluate_valuation(1_080_000.0)
    assert snap.tier == VolatilityTier.THROTTLE
    assert pytest.approx(snap.active_drawdown_pct) == 0.10


def test_liquidity_stress_fee_burn_escalator(safety_breaker: ParametricSafetyBreaker) -> None:
    # Stress factor 0.5 under Throttle regime (base fee 0.20)
    # escalated = min(0.50, 0.20 * (1 + 2.5 * 0.5)) = 0.20 * 2.25 = 0.45 (45%)
    snap = safety_breaker.evaluate_valuation(850_000.0, liquidity_stress_factor=0.5)
    assert pytest.approx(snap.burn_fee_rate) == 0.45

    # Full stress (1.0) under Defense regime: base 0.35 * (1 + 2.5) = 1.225 -> capped at 0.50
    snap = safety_breaker.evaluate_valuation(750_000.0, liquidity_stress_factor=1.0)
    assert snap.burn_fee_rate == 0.50


def test_apply_to_engine(safety_breaker: ParametricSafetyBreaker) -> None:
    engine = FlowStreamEngine()
    engine.register_stream(
        FlowConfig(
            stream_id="s1",
            funder="TREASURY",
            beneficiary="agent-worker",
            role=SwarmRole.GENERAL_WORKER,
            total_allocation=1000.0,
            start_epoch=0.0,
            end_epoch=100.0,
            is_exempt=False,
        )
    )
    engine.register_stream(
        FlowConfig(
            stream_id="s_daemon",
            funder="TREASURY",
            beneficiary="agent-safety",
            role=SwarmRole.SAFETY_DAEMON,
            total_allocation=1000.0,
            start_epoch=0.0,
            end_epoch=100.0,
            is_exempt=True,
        )
    )

    # Trigger Throttle (0.50 multiplier)
    safety_breaker.evaluate_valuation(850_000.0)
    throttled = safety_breaker.apply_to_engine(engine, 10.0)
    assert throttled == 1
    assert engine.registry["s1"].throttle_rate == 0.50
    assert engine.registry["s_daemon"].throttle_rate == 1.00


def test_reset_peak(safety_breaker: ParametricSafetyBreaker) -> None:
    safety_breaker.evaluate_valuation(1_500_000.0)
    assert safety_breaker.peak_capital == 1_500_000.0

    safety_breaker.reset_peak(800_000.0)
    assert safety_breaker.peak_capital == 800_000.0
    assert safety_breaker.snapshot.active_drawdown_pct == 0.0

    with pytest.raises(ValueError, match="New peak capital must be positive"):
        safety_breaker.reset_peak(-10.0)
