"""Unit tests for agent_treasury_stream FastMCP server tools."""

import json
import pytest
from agent_treasury_stream import mcp_server


def test_tool_create_stream_valid() -> None:
    res_str = mcp_server.tool_create_stream(
        stream_id="mcp-stream-1",
        beneficiary="agent-mcp",
        role="EXECUTION_AGENT",
        total_allocation=5000.0,
        duration_days=30.0,
        curve_type="LINEAR",
    )
    res = json.loads(res_str)
    assert res.get("status") == "success"
    assert res.get("stream_id") == "mcp-stream-1"
    assert res.get("beneficiary") == "agent-mcp"


def test_tool_create_stream_invalid_role_or_curve() -> None:
    res_err1 = json.loads(
        mcp_server.tool_create_stream(
            stream_id="err-1",
            beneficiary="agent-err",
            role="INVALID_ROLE",
            total_allocation=1000.0,
        )
    )
    assert "error" in res_err1

    res_err2 = json.loads(
        mcp_server.tool_create_stream(
            stream_id="err-2",
            beneficiary="agent-err",
            role="EXECUTION_AGENT",
            total_allocation=1000.0,
            curve_type="INVALID_CURVE",
        )
    )
    assert "error" in res_err2


def test_tool_get_stream_status_and_withdraw() -> None:
    mcp_server.tool_create_stream(
        stream_id="mcp-stream-w",
        beneficiary="agent-w",
        role="EXECUTION_AGENT",
        total_allocation=86400.0,
        duration_days=1.0,
        curve_type="LINEAR",
    )

    status_str = mcp_server.tool_get_stream_status("mcp-stream-w", current_epoch=43200.0)
    status = json.loads(status_str)
    assert status.get("vested_usd") == 43200.0
    assert status.get("claimable_usd") == 43200.0

    # Withdraw 10,000 USD
    w_str = mcp_server.tool_withdraw_stream("mcp-stream-w", amount_usd=10000.0, current_epoch=43200.0)
    w_res = json.loads(w_str)
    assert w_res.get("status") == "success"
    assert w_res.get("withdrawn_usd") == 10000.0


def test_tool_terminate_stream() -> None:
    mcp_server.tool_create_stream(
        stream_id="mcp-stream-term",
        beneficiary="agent-term",
        role="RESEARCH_AGENT",
        total_allocation=10000.0,
        duration_days=10.0,
        curve_type="LINEAR",
    )
    term_str = mcp_server.tool_terminate_stream("mcp-stream-term", current_epoch=86400.0 * 5)
    term_res = json.loads(term_str)
    assert term_res.get("status") == "cancelled"
    assert term_res.get("final_beneficiary_claim_usd") == 5000.0
    assert term_res.get("treasury_refund_usd") == 5000.0


def test_tool_mint_and_burn_compute_quota() -> None:
    mint_str = mcp_server.tool_mint_compute_quota(agent_id="agent-quota", gross_deposit_usd=1000.0)
    mint_res = json.loads(mint_str)
    assert mint_res.get("status") == "success"
    assert mint_res.get("units_minted") > 0.0

    burn_str = mcp_server.tool_burn_compute_quota(agent_id="agent-quota", units_to_burn=10.0)
    burn_res = json.loads(burn_str)
    assert burn_res.get("status") == "success"
    assert burn_res.get("units_burned") == 10.0


def test_tool_check_portfolio_drift_and_plan_rebalance() -> None:
    drift_str = mcp_server.tool_check_portfolio_drift()
    drift_res = json.loads(drift_str)
    assert "total_value_usd" in drift_res
    assert "drifts" in drift_res

    plan_str = mcp_server.tool_plan_rebalance(current_epoch=0.0, overlay_collars=True)
    plan_res = json.loads(plan_str)
    assert "signals_count" in plan_res
    assert "directives" in plan_res


def test_tool_simulate_swarm() -> None:
    sim_str = mcp_server.tool_simulate_swarm(days=5)
    sim_res = json.loads(sim_str)
    assert "final_portfolio_valuation_usd" in sim_res


def test_create_mcp_server_import_handling() -> None:
    try:
        server = mcp_server.create_mcp_server()
        assert server is not None
    except ImportError:
        pass
