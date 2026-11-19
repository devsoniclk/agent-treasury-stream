"""Model Context Protocol (MCP) server for agent treasury streaming."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.models import FlowCurveType, SwarmRole
from agent_treasury_stream.simulation import SwarmTreasurySimulator

_CONTROLLER = AutonomousTreasuryController()


def tool_create_stream(
    stream_id: str,
    beneficiary: str,
    role: str,
    total_allocation: float,
    duration_days: float = 30.0,
    curve_type: str = "LINEAR",
    exponent: float = 1.0,
    cliff_amount: float = 0.0,
    is_exempt: bool = False,
) -> str:
    """Create a new continuous micro-stream allocation for an agent."""
    try:
        r = SwarmRole(role)
    except ValueError:
        return json.dumps({"error": f"Invalid role '{role}'"})

    try:
        c = FlowCurveType(curve_type)
    except ValueError:
        return json.dumps({"error": f"Invalid curve_type '{curve_type}'"})

    try:
        snap = _CONTROLLER.open_stream(
            stream_id=stream_id,
            beneficiary=beneficiary,
            role=r,
            total_allocation=total_allocation,
            start_epoch=0.0,
            end_epoch=duration_days * 86400.0,
            curve_type=c,
            exponent=exponent,
            cliff_epoch=86400.0 * 5 if cliff_amount > 0 else 0.0,
            cliff_amount=cliff_amount,
            is_exempt=is_exempt,
        )
        return json.dumps({
            "status": "success",
            "stream_id": snap.config.stream_id,
            "beneficiary": snap.config.beneficiary,
            "total_allocation": snap.config.total_allocation,
            "curve_type": snap.config.curve_type.value,
            "is_exempt": snap.config.is_exempt,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_get_stream_status(stream_id: str, current_epoch: float = 86400.0) -> str:
    """Query current vested, claimable, and remaining balances for a stream."""
    try:
        vested = _CONTROLLER.stream_engine.get_vested_balance(stream_id, current_epoch)
        claimable = _CONTROLLER.stream_engine.get_claimable_amount(stream_id, current_epoch)
        remaining = _CONTROLLER.stream_engine.get_remaining_liability(stream_id, current_epoch)
        velocity = _CONTROLLER.stream_engine.get_instantaneous_velocity(stream_id, current_epoch)
        return json.dumps({
            "stream_id": stream_id,
            "current_epoch": current_epoch,
            "vested_usd": vested,
            "claimable_usd": claimable,
            "remaining_liability_usd": remaining,
            "velocity_usd_per_sec": velocity,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_withdraw_stream(
    stream_id: str,
    amount_usd: float,
    current_epoch: float = 86400.0,
) -> str:
    """Execute a withdrawal of claimable funds from an active stream."""
    try:
        withdrawn = _CONTROLLER.stream_engine.execute_withdrawal(
            stream_id=stream_id,
            amount_usd=amount_usd,
            current_epoch=current_epoch,
        )
        return json.dumps({
            "status": "success",
            "stream_id": stream_id,
            "withdrawn_usd": withdrawn,
            "current_epoch": current_epoch,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_terminate_stream(
    stream_id: str,
    current_epoch: float = 86400.0,
) -> str:
    """Terminate and settle a stream, refunding unvested capital to treasury."""
    try:
        claim, refund = _CONTROLLER.stream_engine.terminate_and_settle(stream_id, current_epoch)
        return json.dumps({
            "status": "cancelled",
            "stream_id": stream_id,
            "final_beneficiary_claim_usd": claim,
            "treasury_refund_usd": refund,
            "current_epoch": current_epoch,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_mint_compute_quota(
    agent_id: str,
    gross_deposit_usd: float,
    congestion_index: float = 1.0,
) -> str:
    """Mint compute quota tokens via polynomial bonding curve."""
    try:
        units, fee_burned, avg_price = _CONTROLLER.mint_compute_quota(
            agent_id=agent_id,
            gross_deposit_usd=gross_deposit_usd,
            congestion_index=congestion_index,
        )
        return json.dumps({
            "status": "success",
            "agent_id": agent_id,
            "units_minted": units,
            "fee_burned_usd": fee_burned,
            "average_fill_price": avg_price,
            "circulating_supply": _CONTROLLER.bonding_engine.circulating_supply,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_burn_compute_quota(
    agent_id: str,
    units_to_burn: float,
) -> str:
    """Burn compute quota tokens upon compute job execution."""
    try:
        burned = _CONTROLLER.bonding_engine.burn_units(agent_id, units_to_burn)
        return json.dumps({
            "status": "success",
            "agent_id": agent_id,
            "units_burned": burned,
            "remaining_agent_quota": _CONTROLLER.bonding_engine.allocations[agent_id].units_minted - _CONTROLLER.bonding_engine.allocations[agent_id].units_burned,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_check_portfolio_drift() -> str:
    """Inspect portfolio asset allocation and weight drift."""
    try:
        drifts = _CONTROLLER.rebalancer.compute_drift_deltas()
        needs_rebal, dominant, max_drift = _CONTROLLER.rebalancer.inspect_rebalance_triggers()
        return json.dumps({
            "total_value_usd": _CONTROLLER.rebalancer.get_portfolio_usd_value(),
            "drifts": drifts,
            "needs_rebalance": needs_rebal,
            "max_drift_asset": dominant,
            "max_drift_pct": max_drift,
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_plan_rebalance(
    current_epoch: float = 0.0,
    overlay_collars: bool = False,
) -> str:
    """Generate rebalancing trade directives and delta-neutral collars."""
    try:
        signals = _CONTROLLER.rebalancer.plan_rebalance_orders(
            current_epoch=current_epoch,
            overlay_collar_hedges=overlay_collars,
        )
        return json.dumps({
            "signals_count": len(signals),
            "directives": [s.format_pipeline_directive() for s in signals],
            "raw": [
                {
                    "instrument": s.instrument,
                    "direction": s.direction,
                    "target_entry": s.target_entry,
                    "stop": s.stop_boundary,
                    "profit": s.profit_boundary,
                    "size": s.allocation_size,
                    "memo": s.memo,
                }
                for s in signals
            ]
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def tool_simulate_swarm(days: int = 30) -> str:
    """Run a multi-agent swarm treasury simulation across market shocks."""
    try:
        sim = SwarmTreasurySimulator(simulation_days=days)
        results = sim.run_simulation()
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


def create_mcp_server() -> Any:
    """Create and configure FastMCP server instance if installed."""
    try:
        from fastmcp import FastMCP  # type: ignore
    except ImportError:
        raise ImportError(
            "fastmcp is required to run the MCP server. Install with `pip install agent-treasury-stream[mcp]`"
        )

    mcp = FastMCP("agent-treasury-stream")
    mcp.tool(name="treasury_create_stream")(tool_create_stream)
    mcp.tool(name="treasury_get_stream_status")(tool_get_stream_status)
    mcp.tool(name="treasury_withdraw_stream")(tool_withdraw_stream)
    mcp.tool(name="treasury_terminate_stream")(tool_terminate_stream)
    mcp.tool(name="treasury_mint_compute_quota")(tool_mint_compute_quota)
    mcp.tool(name="treasury_burn_compute_quota")(tool_burn_compute_quota)
    mcp.tool(name="treasury_check_portfolio_drift")(tool_check_portfolio_drift)
    mcp.tool(name="treasury_plan_rebalance")(tool_plan_rebalance)
    mcp.tool(name="treasury_simulate_swarm")(tool_simulate_swarm)
    return mcp


def run_mcp_server() -> None:
    """Run MCP server over stdio transport."""
    server = create_mcp_server()
    server.run()
