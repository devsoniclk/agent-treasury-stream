"""Unit tests for agent_treasury_stream models and enums."""

import pytest
from agent_treasury_stream.models import (
    BondingCurveParams,
    FlowConfig,
    FlowCurveType,
    FlowSnapshot,
    HedgingSignal,
    ReserveHolding,
    SafetyBreakerSnapshot,
    StreamLifecycleState,
    SwarmAllocationRecord,
    SwarmRole,
    VolatilityTier,
)


def test_swarm_role_enum_values() -> None:
    assert SwarmRole.SENTINEL.value == "SENTINEL"
    assert SwarmRole.EXECUTION_AGENT.value == "EXECUTION_AGENT"
    assert SwarmRole.RESEARCH_AGENT.value == "RESEARCH_AGENT"
    assert SwarmRole.SAFETY_DAEMON.value == "SAFETY_DAEMON"
    assert SwarmRole.GENERAL_WORKER.value == "GENERAL_WORKER"


def test_volatility_tier_enum_values() -> None:
    assert VolatilityTier.NOMINAL.value == "NOMINAL"
    assert VolatilityTier.CAUTION.value == "CAUTION"
    assert VolatilityTier.THROTTLE.value == "THROTTLE"
    assert VolatilityTier.DEFENSE.value == "DEFENSE"


def test_flow_curve_type_enum_values() -> None:
    assert FlowCurveType.LINEAR.value == "LINEAR"
    assert FlowCurveType.EXPONENTIAL.value == "EXPONENTIAL"
    assert FlowCurveType.CLIFF.value == "CLIFF"


def test_stream_lifecycle_state_enum_values() -> None:
    assert StreamLifecycleState.PENDING.value == "PENDING"
    assert StreamLifecycleState.ACTIVE.value == "ACTIVE"
    assert StreamLifecycleState.PAUSED.value == "PAUSED"
    assert StreamLifecycleState.CANCELLED.value == "CANCELLED"
    assert StreamLifecycleState.COMPLETED.value == "COMPLETED"


def test_flow_config_valid() -> None:
    cfg = FlowConfig(
        stream_id="test-1",
        funder="TREASURY",
        beneficiary="agent-1",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=1000.0,
        start_epoch=0.0,
        end_epoch=1000.0,
        curve_type=FlowCurveType.LINEAR,
        is_exempt=False,
    )
    assert cfg.stream_id == "test-1"
    assert cfg.total_allocation == 1000.0
    assert not cfg.is_exempt


def test_flow_config_invalid_epochs() -> None:
    with pytest.raises(ValueError, match="end_epoch .* must exceed start_epoch"):
        FlowConfig(
            stream_id="test-err",
            funder="TREASURY",
            beneficiary="agent-1",
            role=SwarmRole.EXECUTION_AGENT,
            total_allocation=1000.0,
            start_epoch=100.0,
            end_epoch=50.0,
        )


def test_flow_config_invalid_allocation() -> None:
    with pytest.raises(ValueError, match="total_allocation must be positive"):
        FlowConfig(
            stream_id="test-err",
            funder="TREASURY",
            beneficiary="agent-1",
            role=SwarmRole.EXECUTION_AGENT,
            total_allocation=-10.0,
            start_epoch=0.0,
            end_epoch=100.0,
        )


def test_flow_config_invalid_cliff() -> None:
    with pytest.raises(ValueError, match="cliff_amount must be between 0 and total_allocation"):
        FlowConfig(
            stream_id="test-err",
            funder="TREASURY",
            beneficiary="agent-1",
            role=SwarmRole.EXECUTION_AGENT,
            total_allocation=100.0,
            start_epoch=0.0,
            end_epoch=100.0,
            cliff_amount=150.0,
        )

    with pytest.raises(ValueError, match="cliff_epoch must be between start and end epochs"):
        FlowConfig(
            stream_id="test-err",
            funder="TREASURY",
            beneficiary="agent-1",
            role=SwarmRole.EXECUTION_AGENT,
            total_allocation=100.0,
            start_epoch=10.0,
            end_epoch=100.0,
            cliff_amount=20.0,
            cliff_epoch=5.0,
        )


def test_reserve_holding_properties() -> None:
    rh = ReserveHolding(
        ticker="ETH",
        units=10.0,
        unit_price_usd=2500.0,
        target_weight=0.25,
        current_weight=0.25,
    )
    assert rh.total_usd_value == 25000.0
    assert not rh.is_hedged


def test_hedging_signal_formatting() -> None:
    sig = HedgingSignal(
        instrument="ETH-PERP",
        direction="HEDGE_SHORT",
        target_entry=2499.0,
        stop_boundary=2600.0,
        profit_boundary=2300.0,
        leverage=1.0,
        expected_rr=2.0,
        allocation_size=10.0,
        epoch=1000.0,
        memo="Collar hedge",
    )
    formatted = sig.format_pipeline_directive()
    assert "ETH-PERP | HEDGE_SHORT | 2499.0000 | 2600.0000 | 2300.0000 | 1.0x | 2.00 | 10.00" == formatted
