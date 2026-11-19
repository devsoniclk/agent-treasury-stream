"""Benchmark harness comparing static lump-sum vs micro-streaming architectures."""

import time
from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.simulation import SwarmTreasurySimulator


def benchmark_simulation_throughput() -> None:
    print("=== Benchmarking Swarm Treasury Simulation Throughput ===")
    start = time.perf_counter()
    sim = SwarmTreasurySimulator(simulation_days=30)
    results = sim.run_simulation()
    duration = time.perf_counter() - start

    ticks = 30 * 24
    tps = ticks / duration
    print(f"Executed 30 days ({ticks} hourly ticks) in {duration:.4f}s ({tps:,.1f} ticks/sec)")
    print(f"Final Portfolio Valuation: ${results['final_portfolio_valuation_usd']:,.2f}")
    print(f"Fee Burned: ${results['cumulative_fee_burned_usd']:,.2f}")
    print(f"Max Drawdown: {results['max_drawdown_pct']*100:.2f}%")


def benchmark_bonding_curve_solves() -> None:
    print("\n=== Benchmarking Bonding Curve Newton-Raphson Solver ===")
    controller = AutonomousTreasuryController()
    start = time.perf_counter()
    n_solves = 10_000
    for i in range(n_solves):
        deposit = 100.0 + (i % 500)
        controller.bonding_engine.solve_units_for_deposit(deposit)
    duration = time.perf_counter() - start
    print(f"Completed {n_solves:,} closed-form integral solves in {duration:.4f}s ({n_solves/duration:,.1f} solves/sec)")


if __name__ == "__main__":
    benchmark_simulation_throughput()
    benchmark_bonding_curve_solves()
