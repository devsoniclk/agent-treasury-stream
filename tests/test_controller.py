"""Unit tests for AutonomousTreasuryController master coordinator."""

import pytest
from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.models import (
    FlowCurveType,
    SwarmRole,
    VolatilityTier,
)


@pytest.fixture
def controller() -> AutonomousTreasuryController:
    return AutonomousTreasuryController()


def test_open_stream_backed_by_usdc(controller: AutonomousTreasuryController) -> None:
    initial_usdc = controller.rebalancer.holdings["USDC"].units
    allocation = 20_000.0

    snap = controller.open_stream(
        stream_id="stream-1",
        beneficiary="agent-worker",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=allocation,
        start_epoch=0.0,
        end_epoch=86400.0 * 30,
        curve_type=FlowCurveType.LINEAR,
    )
    assert snap.config.stream_id == "stream-1"
    # Free USDC was deducted from unallocated pool
    assert controller.rebalancer.holdings["USDC"].units == initial_usdc - allocation


def test_open_stream_insolvency_check(controller: AutonomousTreasuryController) -> None:
    # Attempting to allocate more than total free USDC fails
    huge_allocation = 1_000_000.0
    with pytest.raises(ValueError, match="Insolvent: free USDC"):
        controller.open_stream(
            stream_id="stream-huge",
            beneficiary="agent-whale",
            role=SwarmRole.EXECUTION_AGENT,
            total_allocation=huge_allocation,
            start_epoch=0.0,
            end_epoch=86400.0,
        )


def test_mint_compute_quota_with_controller(controller: AutonomousTreasuryController) -> None:
    units, fee_burned, avg_price = controller.mint_compute_quota(
        agent_id="agent-01", gross_deposit_usd=1_000.0
    )
    assert units > 0.0
    assert fee_burned > 0.0
    assert avg_price > 0.0
    assert controller.bonding_engine.circulating_supply == units


def test_sync_treasury_state(controller: AutonomousTreasuryController) -> None:
    controller.open_stream(
        stream_id="stream-test",
        beneficiary="agent-test",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=10_000.0,
        start_epoch=0.0,
        end_epoch=86400.0,
    )

    # Initial sync
    val, tier, dd = controller.sync_treasury_state(current_epoch=100.0)
    assert val > 0.0
    assert tier == VolatilityTier.NOMINAL
    assert dd < 0.001  # Drawdown is negligible (only ~0.001% due to elapsed unwithdrawn vesting)

    # Simulate price collapse on ETH
    controller.rebalancer.refresh_price("ETH", 1000.0)
    val2, tier2, dd2 = controller.sync_treasury_state(current_epoch=200.0, liquidity_stress=0.5)
    assert val2 < val
    assert dd2 > 0.0
