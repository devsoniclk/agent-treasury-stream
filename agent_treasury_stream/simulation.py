"""Swarm treasury simulator modeling autonomous agent cashflows and volatility."""

from __future__ import annotations

from typing import Dict, List, Optional
from agent_treasury_stream.models import (
    FlowCurveType,
    SwarmRole,
    VolatilityTier,
)
from agent_treasury_stream.controller import AutonomousTreasuryController


class SwarmTreasurySimulator:
    """Simulates a multi-agent swarm operating over discrete time horizons."""

    def __init__(self, simulation_days: int = 30) -> None:
        self.simulation_days = simulation_days
        self.total_seconds = simulation_days * 86400
        self.step_seconds = 3600  # 1 hour per simulation tick
        self.controller = AutonomousTreasuryController()

        # 10 Swarm Agents
        self.agent_roster = [
            ("agent-01-sentinel", SwarmRole.SENTINEL, 6_000.0, FlowCurveType.LINEAR, 1.0, 0.0, False),
            ("agent-02-execution-1", SwarmRole.EXECUTION_AGENT, 9_000.0, FlowCurveType.LINEAR, 1.0, 0.0, False),
            ("agent-03-execution-2", SwarmRole.EXECUTION_AGENT, 9_000.0, FlowCurveType.LINEAR, 1.0, 0.0, False),
            ("agent-04-research", SwarmRole.RESEARCH_AGENT, 4_500.0, FlowCurveType.EXPONENTIAL, 1.5, 0.0, False),
            ("agent-05-trainer-1", SwarmRole.RESEARCH_AGENT, 15_000.0, FlowCurveType.EXPONENTIAL, 2.0, 0.0, False),
            ("agent-06-trainer-2", SwarmRole.RESEARCH_AGENT, 12_000.0, FlowCurveType.EXPONENTIAL, 2.0, 0.0, False),
            ("agent-07-arb-1", SwarmRole.EXECUTION_AGENT, 7_500.0, FlowCurveType.CLIFF, 1.0, 1_500.0, False),
            ("agent-08-arb-2", SwarmRole.EXECUTION_AGENT, 7_500.0, FlowCurveType.LINEAR, 1.0, 0.0, False),
            ("agent-09-safety-daemon", SwarmRole.SAFETY_DAEMON, 6_000.0, FlowCurveType.LINEAR, 1.0, 0.0, True),  # Exempt!
            ("agent-10-worker", SwarmRole.GENERAL_WORKER, 3_500.0, FlowCurveType.LINEAR, 1.0, 0.0, False),
        ]

    def setup_swarm_streams(self, start_epoch: float = 0.0) -> None:
        """Initializes all agent streams across the swarm."""
        end_epoch = start_epoch + self.total_seconds
        for agent_id, role, allocation, curve_type, exponent, cliff_amt, is_exempt in self.agent_roster:
            cliff_epoch = start_epoch + (self.total_seconds * 0.15) if cliff_amt > 0.0 else 0.0
            self.controller.open_stream(
                stream_id=f"stream-{agent_id}",
                beneficiary=agent_id,
                role=role,
                total_allocation=allocation,
                start_epoch=start_epoch,
                end_epoch=end_epoch,
                curve_type=curve_type,
                exponent=exponent,
                cliff_epoch=cliff_epoch,
                cliff_amount=cliff_amt,
                is_exempt=is_exempt,
            )

    def run_simulation(self) -> Dict[str, float]:
        """Runs the complete multi-day simulation loop with shocks and rebalancing."""
        self.setup_swarm_streams(0.0)

        current_time = 0.0
        total_steps = self.total_seconds // self.step_seconds

        for step in range(total_steps):
            current_time = step * self.step_seconds
            day = current_time / 86400.0

            # Synthetic market stress on Day 12 to 16
            eth_price = 2500.0
            sol_price = 150.0
            stress = 0.0

            if 12.0 <= day <= 16.0:
                crash_pct = min(0.35, 0.07 * (day - 11.0))
                eth_price = 2500.0 * (1.0 - crash_pct)
                sol_price = 150.0 * (1.0 - crash_pct)
                stress = min(1.0, crash_pct * 2.5)

            self.controller.rebalancer.refresh_price("ETH", eth_price)
            self.controller.rebalancer.refresh_price("SOL", sol_price)

            # Sync controller state
            val, tier, dd = self.controller.sync_treasury_state(current_time, liquidity_stress=stress)

            # Periodic agent compute mints
            if step % 24 == 0 and step > 0:
                for agent_id, _, _, _, _, _, _ in self.agent_roster[:5]:
                    stream_id = f"stream-{agent_id}"
                    claimable = self.controller.stream_engine.get_claimable_amount(stream_id, current_time)
                    if claimable >= 100.0:
                        w_amt = min(claimable, 200.0)
                        self.controller.stream_engine.execute_withdrawal(stream_id, w_amt, current_time)
                        self.controller.mint_compute_quota(agent_id, w_amt * 0.8)

            # Check rebalance orders
            if step % 12 == 0:
                orders = self.controller.rebalancer.plan_rebalance_orders(current_time)
                for order in orders:
                    self.controller.rebalancer.record_execution(order)

        final_val = self.controller.rebalancer.get_portfolio_usd_value()
        burned_usd = self.controller.bonding_engine.cumulative_fee_burned_usd
        max_dd = self.controller.safety_breaker.snapshot.active_drawdown_pct

        return {
            "final_portfolio_valuation_usd": final_val,
            "cumulative_fee_burned_usd": burned_usd,
            "max_drawdown_pct": max_dd,
            "circulating_compute_supply": self.controller.bonding_engine.circulating_supply,
        }
