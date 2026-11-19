"""End-to-end demonstration of autonomous agent swarm treasury lifecycle."""

import time
from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.models import FlowCurveType, SwarmRole


def main() -> None:
    print("=" * 70)
    print("  AUTONOMOUS AGENT TREASURY STREAMING: LIFECYCLE DEMONSTRATION")
    print("=" * 70)

    controller = AutonomousTreasuryController()
    start_time = 0.0
    horizon_seconds = 86400.0 * 30.0  # 30 days

    print("\n1. Initializing Multi-Agent Cashflow Streams...")
    # Sentinel agent (Linear stream)
    s1 = controller.open_stream(
        stream_id="stream-sentinel-01",
        beneficiary="agent-sentinel-01",
        role=SwarmRole.SENTINEL,
        total_allocation=10_000.0,
        start_epoch=start_time,
        end_epoch=start_time + horizon_seconds,
        curve_type=FlowCurveType.LINEAR,
    )
    print(f"  - Registered {s1.config.stream_id}: ${s1.config.total_allocation:,.2f} over 30 days")

    # Safety Daemon (Exempt critical stream)
    s2 = controller.open_stream(
        stream_id="stream-safety-daemon",
        beneficiary="daemon-safety-01",
        role=SwarmRole.SAFETY_DAEMON,
        total_allocation=6_000.0,
        start_epoch=start_time,
        end_epoch=start_time + horizon_seconds,
        curve_type=FlowCurveType.LINEAR,
        is_exempt=True,
    )
    print(f"  - Registered {s2.config.stream_id}: ${s2.config.total_allocation:,.2f} [EXEMPT]")

    print("\n2. Advancing Time to Day 5 & Auditing Vesting...")
    day_5 = 86400.0 * 5.0
    v1 = controller.stream_engine.get_vested_balance(s1.config.stream_id, day_5)
    c1 = controller.stream_engine.get_claimable_amount(s1.config.stream_id, day_5)
    print(f"  - Day 5 Vested: ${v1:,.2f} | Claimable: ${c1:,.2f}")

    print("\n3. Agent Withdrawing Funds & Minting Compute Quota...")
    withdrawn = controller.stream_engine.execute_withdrawal(s1.config.stream_id, 1_000.0, day_5)
    units, fee_burned, avg_price = controller.mint_compute_quota(
        agent_id="agent-sentinel-01",
        gross_deposit_usd=withdrawn,
    )
    print(f"  - Withdrawn: ${withdrawn:,.2f}")
    print(f"  - Minted: {units:,.2f} compute units @ avg ${avg_price:.4f} USD")
    print(f"  - Fee Burned: ${fee_burned:,.2f} USD")

    print("\n4. Simulating Market Flash Crash & Circuit Breaker Response...")
    controller.rebalancer.refresh_price("ETH", 1750.0)  # -30% crash
    controller.rebalancer.refresh_price("SOL", 100.0)   # -33% crash
    val, tier, dd = controller.sync_treasury_state(day_5, liquidity_stress=0.50)
    print(f"  - Valuation post-crash: ${val:,.2f}")
    print(f"  - Drawdown: {dd*100:.2f}% | Safety Tier: {tier.value}")
    print(f"  - Standard Stream Throttle: {controller.stream_engine.registry['stream-sentinel-01'].throttle_rate * 100:.1f}%")
    print(f"  - Exempt Daemon Throttle: {controller.stream_engine.registry['stream-safety-daemon'].throttle_rate * 100:.1f}%")

    print("\n5. Generating Rebalance Directives...")
    orders = controller.rebalancer.plan_rebalance_orders(day_5)
    for ord in orders:
        print(f"  - Directive: {ord.format_pipeline_directive()}")

    print("\nLifecycle demonstration concluded successfully.")


if __name__ == "__main__":
    main()
