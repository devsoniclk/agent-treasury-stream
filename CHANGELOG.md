# Changelog

All notable changes to `agent-treasury-stream` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-11-19

### Added
- **Core Micro-Streaming Engine (`FlowStreamEngine`)**: Sub-second continuous cashflow streaming supporting Linear, Exponential, and Cliff curves with dynamic throttling.
- **Polynomial Bonding Curve Engine (`ComputeBondingEngine`)**: Closed-form integral reserves, Newton-Raphson unit pricing for compute quotas, congestion pricing, and dynamic fee burn mechanisms.
- **Parametric Safety Breakers (`ParametricSafetyBreaker`)**: High water mark drawdown monitoring across four volatility tiers (Nominal, Caution, Throttle, Defense) with critical service exemption invariants (`SAFETY_DAEMON`).
- **Dynamic Liquidity-Drain Fee Burn Escalator**: Automatic fee burn escalation ($f_{\text{burn}} \le 50\%$) under external liquidity drain conditions.
- **Multi-Asset Rebalancer (`TreasuryRebalancer`)**: Target weight drift detection, 0.05% orderbook execution buffer, and delta-neutral perp collar hedging.
- **Autonomous Swarm Simulator (`SwarmTreasurySimulator`)**: 10-agent swarm financial simulation over 30-day time horizons with synthetic market shock testing.
- **Unified Master Controller (`AutonomousTreasuryController`)**: Synchronized state management bridging reserves, streams, bonding curves, and solvency runway auditing.
- **FastMCP Protocol Suite (`mcp_server.py`)**: 9 Model Context Protocol tools for AI agent tool execution and automated governance.
- **Production CLI (`cli.py`)**: Rich-powered commands for simulation, curve pricing, and portfolio drift inspection.
- **Exhaustive Automated Test Suite**: Comprehensive unit and integration test coverage across all mathematical models and state machines.
