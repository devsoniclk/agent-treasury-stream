"""Example: Multi-asset treasury drift rebalancing and delta-neutral collars."""

from agent_treasury_stream.controller import AutonomousTreasuryController


def main() -> None:
    print("=== Multi-Asset Treasury Rebalancing & Hedging Demo ===")
    controller = AutonomousTreasuryController()

    print(f"Initial Portfolio Value: ${controller.rebalancer.get_portfolio_usd_value():,.2f}")
    drifts = controller.rebalancer.compute_drift_deltas()
    print("Initial Asset Drifts:", {k: f"{v*100:.2f}%" for k, v in drifts.items()})

    # Simulate ETH rally (+60%) and SOL decline (-30%)
    print("\nSimulating market divergence: ETH -> $4,000 (+60%), SOL -> $105 (-30%)...")
    controller.rebalancer.refresh_price("ETH", 4_000.0)
    controller.rebalancer.refresh_price("SOL", 105.0)

    print(f"New Portfolio Value: ${controller.rebalancer.get_portfolio_usd_value():,.2f}")
    drifts_after = controller.rebalancer.compute_drift_deltas()
    print("Updated Asset Drifts:", {k: f"{v*100:.2f}%" for k, v in drifts_after.items()})

    needs_rebal, dominant, max_drift = controller.rebalancer.inspect_rebalance_triggers()
    print(f"Rebalance Triggered: {needs_rebal} (Dominant Asset: {dominant}, Max Drift: {max_drift*100:.2f}%)")

    # Generate pipeline rebalance orders with delta-neutral collar overlays
    orders = controller.rebalancer.plan_rebalance_orders(current_epoch=100.0, overlay_collar_hedges=True)
    print(f"\nGenerated {len(orders)} Execution Directives:")
    for order in orders:
        print(f"  -> {order.format_pipeline_directive()}")
        print(f"     Memo: {order.memo}")


if __name__ == "__main__":
    main()
