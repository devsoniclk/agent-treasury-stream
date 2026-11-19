"""Example: Complete lifecycle of autonomous micro-streaming with throttling."""

from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.models import FlowCurveType, SwarmRole


def main() -> None:
    print("=== Agent Treasury Micro-Streaming Lifecycle Demo ===")
    controller = AutonomousTreasuryController()

    # 1. Open linear stream for execution agent
    stream_id = "stream-exec-01"
    allocation = 10_000.0  # $10,000 USD
    duration_days = 30.0
    start_time = 0.0
    end_time = duration_days * 86400.0

    print(f"Opening stream '{stream_id}' with ${allocation:,.2f} over {duration_days} days...")
    snap = controller.open_stream(
        stream_id=stream_id,
        beneficiary="agent-alpha",
        role=SwarmRole.EXECUTION_AGENT,
        total_allocation=allocation,
        start_epoch=start_time,
        end_epoch=end_time,
        curve_type=FlowCurveType.LINEAR,
    )

    # 2. Inspect progression at Day 10
    epoch_day_10 = 10.0 * 86400.0
    vested_10 = controller.stream_engine.get_vested_balance(stream_id, epoch_day_10)
    claimable_10 = controller.stream_engine.get_claimable_amount(stream_id, epoch_day_10)
    print(f"Day 10: Vested = ${vested_10:,.2f}, Claimable = ${claimable_10:,.2f}")

    # 3. Agent withdraws $2,000
    withdrawn = controller.stream_engine.execute_withdrawal(stream_id, 2_000.0, epoch_day_10)
    remaining_claimable = controller.stream_engine.get_claimable_amount(stream_id, epoch_day_10)
    print(f"Withdrawal executed: ${withdrawn:,.2f}, Remaining Claimable = ${remaining_claimable:,.2f}")

    # 4. Trigger circuit breaker throttle (simulating market crash)
    print("\nSimulating market crash (drawdown trigger)...")
    controller.safety_breaker.evaluate_valuation(current_valuation=850_000.0)  # ~15% drawdown
    controller.safety_breaker.apply_to_engine(controller.stream_engine, epoch_day_10)
    throttle_rate = controller.stream_engine.registry[stream_id].throttle_rate
    print(f"Safety breaker active. Stream throttle rate = {throttle_rate * 100:.1f}%")

    # 5. Check velocity at Day 15 under throttle
    epoch_day_15 = 15.0 * 86400.0
    vested_15 = controller.stream_engine.get_vested_balance(stream_id, epoch_day_15)
    velocity = controller.stream_engine.get_instantaneous_velocity(stream_id, epoch_day_15)
    print(f"Day 15 (Throttled): Vested = ${vested_15:,.2f}, Instantaneous Velocity = ${velocity * 86400:,.2f}/day")


if __name__ == "__main__":
    main()
