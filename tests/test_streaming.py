"""Unit tests for the FlowStreamEngine continuous micro-streaming engine."""

import pytest
from agent_treasury_stream.models import (
    FlowConfig,
    FlowCurveType,
    StreamLifecycleState,
    SwarmRole,
)
from agent_treasury_stream.streaming import FlowStreamEngine


@pytest.fixture
def stream_engine() -> FlowStreamEngine:
    return FlowStreamEngine()


def test_register_and_query_stream(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s1",
        funder="TREASURY",
        beneficiary="agent-alpha",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=3000.0,
        start_epoch=0.0,
        end_epoch=3000.0,
    )
    snap = stream_engine.register_stream(cfg)
    assert snap.status == StreamLifecycleState.ACTIVE
    assert snap.config.stream_id == "s1"
    assert stream_engine.get_vested_balance("s1", 0.0) == 0.0
    assert stream_engine.get_remaining_liability("s1", 0.0) == 3000.0


def test_duplicate_registration_fails(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s1",
        funder="TREASURY",
        beneficiary="agent-alpha",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=1000.0,
    )
    stream_engine.register_stream(cfg)
    with pytest.raises(ValueError, match="already registered"):
        stream_engine.register_stream(cfg)


def test_linear_vesting_progression(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_linear",
        funder="TREASURY",
        beneficiary="agent-alpha",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=1000.0,
        start_epoch=100.0,
        end_epoch=200.0,
        curve_type=FlowCurveType.LINEAR,
    )
    stream_engine.register_stream(cfg)

    # Before start
    assert stream_engine.get_vested_balance("s_linear", 50.0) == 0.0
    # Midway
    assert pytest.approx(stream_engine.get_vested_balance("s_linear", 150.0)) == 500.0
    # At end
    assert pytest.approx(stream_engine.get_vested_balance("s_linear", 200.0)) == 1000.0
    # Beyond end
    assert pytest.approx(stream_engine.get_vested_balance("s_linear", 300.0)) == 1000.0


def test_exponential_vesting_progression(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_exp",
        funder="TREASURY",
        beneficiary="agent-beta",
        role=SwarmRole.RESEARCH_AGENT,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
        curve_type=FlowCurveType.EXPONENTIAL,
        exponent=2.0,  # Quadratic: progress = (t/T)^2
    )
    stream_engine.register_stream(cfg)

    # At 50% time, progress is (0.5)^2 = 0.25 -> 250 USD
    assert pytest.approx(stream_engine.get_vested_balance("s_exp", 50.0)) == 250.0
    # At 100% time -> 1000 USD
    assert pytest.approx(stream_engine.get_vested_balance("s_exp", 100.0)) == 1000.0


def test_cliff_vesting_progression(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_cliff",
        funder="TREASURY",
        beneficiary="agent-gamma",
        role=SwarmRole.GENERAL_WORKER,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
        curve_type=FlowCurveType.CLIFF,
        cliff_epoch=20.0,
        cliff_amount=200.0,
    )
    stream_engine.register_stream(cfg)

    # Before cliff epoch
    assert stream_engine.get_vested_balance("s_cliff", 10.0) == 0.0
    # Exactly at cliff epoch: cliff amount unlocked (200) + linear progression for 20/100 of remaining 800 (160) = 360
    vested_cliff = stream_engine.get_vested_balance("s_cliff", 20.0)
    assert pytest.approx(vested_cliff) == 360.0
    # At end epoch
    assert pytest.approx(stream_engine.get_vested_balance("s_cliff", 100.0)) == 1000.0


def test_withdrawals_and_claimable(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_w",
        funder="TREASURY",
        beneficiary="agent-delta",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
    )
    stream_engine.register_stream(cfg)

    assert stream_engine.get_claimable_amount("s_w", 50.0) == 500.0

    # Withdraw 200
    withdrawn = stream_engine.execute_withdrawal("s_w", 200.0, 50.0)
    assert withdrawn == 200.0
    assert stream_engine.get_claimable_amount("s_w", 50.0) == 300.0

    # Over-withdrawal fails
    with pytest.raises(ValueError, match="Cannot withdraw"):
        stream_engine.execute_withdrawal("s_w", 400.0, 50.0)

    # Negative withdrawal fails
    with pytest.raises(ValueError, match="Withdrawal amount must be strictly positive"):
        stream_engine.execute_withdrawal("s_w", -10.0, 50.0)


def test_pause_and_resume_stream(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_p",
        funder="TREASURY",
        beneficiary="agent-eps",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
    )
    stream_engine.register_stream(cfg)

    # Progress to t=40 -> 400 vested
    assert pytest.approx(stream_engine.get_vested_balance("s_p", 40.0)) == 400.0

    # Pause at t=40
    stream_engine.pause_flow("s_p", 40.0)
    assert stream_engine.registry["s_p"].status == StreamLifecycleState.PAUSED

    # Query at t=60 while paused: should still be 400
    assert pytest.approx(stream_engine.get_vested_balance("s_p", 60.0)) == 400.0

    # Resume at t=60
    stream_engine.resume_flow("s_p", 60.0)
    assert stream_engine.registry["s_p"].status == StreamLifecycleState.ACTIVE

    # Progress to t=80 (20s active since resume) -> 400 + 200 = 600
    assert pytest.approx(stream_engine.get_vested_balance("s_p", 80.0)) == 600.0


def test_throttling_and_critical_exemption(stream_engine: FlowStreamEngine) -> None:
    cfg_normal = FlowConfig(
        stream_id="s_norm",
        funder="TREASURY",
        beneficiary="agent-worker",
        role=SwarmRole.GENERAL_WORKER,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
        is_exempt=False,
    )
    cfg_exempt = FlowConfig(
        stream_id="s_exempt",
        funder="TREASURY",
        beneficiary="agent-safety",
        role=SwarmRole.SAFETY_DAEMON,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
        is_exempt=True,
    )
    stream_engine.register_stream(cfg_normal)
    stream_engine.register_stream(cfg_exempt)

    # Set 50% throttle at t=20
    stream_engine.set_throttle("s_norm", 0.50, 20.0)
    stream_engine.set_throttle("s_exempt", 0.50, 20.0)

    # Normal stream receives 50% throttle, exempt remains 1.0
    assert stream_engine.registry["s_norm"].throttle_rate == 0.50
    assert stream_engine.registry["s_exempt"].throttle_rate == 1.00

    # At t=40:
    # normal: 200 (first 20s @ 10/s) + 100 (next 20s @ 5/s) = 300
    # exempt: 400 (40s @ 10/s) = 400
    assert pytest.approx(stream_engine.get_vested_balance("s_norm", 40.0)) == 300.0
    assert pytest.approx(stream_engine.get_vested_balance("s_exempt", 40.0)) == 400.0


def test_invalid_throttle_rate(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_t",
        funder="TREASURY",
        beneficiary="agent-worker",
        role=SwarmRole.GENERAL_WORKER,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
    )
    stream_engine.register_stream(cfg)
    with pytest.raises(ValueError, match="Throttle rate must be bounded"):
        stream_engine.set_throttle("s_t", 1.5, 10.0)
    with pytest.raises(ValueError, match="Throttle rate must be bounded"):
        stream_engine.set_throttle("s_t", -0.1, 10.0)


def test_terminate_and_settle(stream_engine: FlowStreamEngine) -> None:
    cfg = FlowConfig(
        stream_id="s_term",
        funder="TREASURY",
        beneficiary="agent-term",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=100.0,
    )
    stream_engine.register_stream(cfg)

    # At t=30: 300 vested. Beneficiary withdraws 100
    stream_engine.execute_withdrawal("s_term", 100.0, 30.0)

    # At t=50: terminate
    claim, refund = stream_engine.terminate_and_settle("s_term", 50.0)
    # Vested at 50 is 500. Already withdrawn 100 -> claim = 400.
    # Unvested is 500 -> refund = 500.
    assert pytest.approx(claim) == 400.0
    assert pytest.approx(refund) == 500.0
    assert stream_engine.registry["s_term"].status == StreamLifecycleState.CANCELLED

    # Subsequent termination returns 0, 0
    c2, r2 = stream_engine.terminate_and_settle("s_term", 60.0)
    assert c2 == 0.0 and r2 == 0.0


def test_solvency_runway_calculation(stream_engine: FlowStreamEngine) -> None:
    cfg1 = FlowConfig(
        stream_id="s_run1",
        funder="TREASURY",
        beneficiary="agent-1",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=86400.0,  # 1 USD/sec
        start_epoch=0.0,
        end_epoch=86400.0,
    )
    cfg2 = FlowConfig(
        stream_id="s_run2",
        funder="TREASURY",
        beneficiary="agent-2",
        role=SwarmRole.RESEARCH_AGENT,
        total_allocation=86400.0 * 2,  # 2 USD/sec
        start_epoch=0.0,
        end_epoch=86400.0,
    )
    stream_engine.register_stream(cfg1)
    stream_engine.register_stream(cfg2)

    # Combined burn velocity: 3 USD/sec
    assert pytest.approx(stream_engine.calculate_aggregate_burn_rate(100.0)) == 3.0

    # Runway over 1000 seconds requires 3000 USD
    is_solvent, req, ratio = stream_engine.check_solvency_runway(
        liquid_reserves_usd=3000.0, horizon_seconds=1000.0, current_epoch=100.0
    )
    assert is_solvent
    assert req == 3000.0
    assert pytest.approx(ratio) == 1.0

    is_insolvent, _, ratio2 = stream_engine.check_solvency_runway(
        liquid_reserves_usd=1500.0, horizon_seconds=1000.0, current_epoch=100.0
    )
    assert not is_insolvent
    assert pytest.approx(ratio2) == 0.5
