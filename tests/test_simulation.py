"""Unit tests for SwarmTreasurySimulator."""

import pytest
from agent_treasury_stream.simulation import SwarmTreasurySimulator


def test_swarm_simulation_execution() -> None:
    sim = SwarmTreasurySimulator(simulation_days=15)
    results = sim.run_simulation()

    assert "final_portfolio_valuation_usd" in results
    assert "cumulative_fee_burned_usd" in results
    assert "max_drawdown_pct" in results
    assert "circulating_compute_supply" in results

    assert results["final_portfolio_valuation_usd"] > 0.0
    assert results["cumulative_fee_burned_usd"] > 0.0
    assert results["max_drawdown_pct"] >= 0.0
    assert results["circulating_compute_supply"] > 0.0


def test_swarm_agent_roster_initialization() -> None:
    sim = SwarmTreasurySimulator(simulation_days=5)
    sim.setup_swarm_streams(0.0)

    # 10 agents registered in controller
    assert len(sim.controller.stream_engine.registry) == 10

    # Safety daemon stream is exempt
    safety_snap = sim.controller.stream_engine.registry["stream-agent-09-safety-daemon"]
    assert safety_snap.config.is_exempt
