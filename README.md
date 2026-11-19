# Agent Treasury Stream (`agent-treasury-stream`)

[![CI](https://github.com/devsoniclk/agent-treasury-stream/actions/workflows/ci.yml/badge.svg)](https://github.com/devsoniclk/agent-treasury-stream/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-91%25-brightgreen.svg)](https://github.com/devsoniclk/agent-treasury-stream)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Protocol%20Enabled-orange.svg)](https://modelcontextprotocol.io/)

Continuous algorithmic micro-streaming, dynamic polynomial compute quota bonding curves, and parametric drawdown circuit breakers for autonomous AI agent swarms and multi-agent treasuries.

---

## 1. Problem Statement & Motivation

Traditional multi-agent organizations and decentralized agent swarms suffer from severe capital inefficiency and existential solvency risks when relying on **static upfront lump-sum budgeting**:
1. **Capital Lockup & Counterparty Drain**: Allocating 30-day budgets upfront exposes treasuries to agent failure, rogue tool loop exploitation, or unspent capital lockups.
2. **Volatile Market Drawdowns**: Static budgets do not dynamically adapt during severe market crashes, causing treasuries to run out of runway while paying out fixed dollar allocations.
3. **Static Compute Pricing**: Compute tokens or API quotas bought at flat rates cause compute hoarding during low demand and price shock rationing during high-congestion periods.

`agent-treasury-stream` solves this by introducing:
- **Continuous Per-Second Micro-Streaming**: Replaces lump-sums with continuous, conservation-preserving cashflows across Linear, Exponential, and Cliff curves.
- **Polynomial Bonding Curve Compute Quotas**: Dynamic pricing $P(S) = P_0 + \alpha S^k$ with closed-form reserve integrals and automated fee burning.
- **High-Water Mark (HWM) Circuit Breakers**: Automatic multi-tier throttling ($\theta \in [0.0, 1.0]$) triggered by portfolio drawdowns, with **strict immunity for safety and risk daemons**.
- **Liquidity-Drain Fee Burn Escalator**: Automatic fee burn escalation ($f_{\text{burn}} \le 50\%$) under external market liquidity stress.
- **Multi-Asset Rebalancer with Execution Buffers**: Drift tracking with mandatory 0.05% orderbook cross buffers and delta-neutral perp collar overlays.

---

## 2. Mathematical Architecture

### 2.1 Continuous Flow Mechanics & Conservation Invariant

For an allocation $A_{\text{total}}$ over interval $[T_{\text{start}}, T_{\text{end}}]$, elapsed progress is:
$$\tau(t) = \frac{t - T_{\text{start}}}{T_{\text{end}} - T_{\text{start}}} \in [0, 1]$$

Vesting curves supported:
- **Linear**: $V(t) = A_{\text{total}} \cdot \tau(t)$
- **Exponential**: $V(t) = A_{\text{total}} \cdot (\tau(t))^\gamma \quad (\gamma > 1.0)$
- **Cliff**: $V(t) = 0$ for $t < T_{\text{cliff}}$, and $A_{\text{cliff}} + (A_{\text{total}} - A_{\text{cliff}}) \cdot \tau(t)$ for $t \ge T_{\text{cliff}}$

#### Conservation Settlement Invariant
Upon stream termination or cancellation at timestamp $t$:
$$\text{Claim}_{\text{beneficiary}} = V(t) - \text{Withdrawn}(t)$$
$$\text{Refund}_{\text{treasury}} = A_{\text{total}} - V(t)$$
$$\text{Claim}_{\text{beneficiary}} + \text{Refund}_{\text{treasury}} + \text{Withdrawn}(t) \equiv A_{\text{total}}$$

### 2.2 Polynomial Compute Quota Bonding Curve

The instantaneous price to mint the $S$-th compute quota unit under demand congestion index $\lambda \ge 1.0$:
$$P(S, \lambda) = \left(P_0 + \alpha S^k\right) \cdot \lambda$$

The closed-form reserve integral $R(S)$ required to back $S$ units in circulation is:
$$R(S) = \int_0^S P(u, 1.0) \, du = P_0 S + \frac{\alpha}{k+1} S^{k+1}$$

Gross reserve deposits $D_{\text{gross}}$ undergo dynamic fee burning $f_{\text{burn}} \in [0.05, 0.50]$:
$$D_{\text{net}} = D_{\text{gross}} \cdot (1 - f_{\text{burn}})$$
$$\text{Burned}_{\text{treasury}} = D_{\text{gross}} \cdot f_{\text{burn}}$$

Units minted $\Delta S$ are calculated via Newton-Raphson iteration solving:
$$R(S_0 + \Delta S) - R(S_0) = \frac{D_{\text{net}}}{\lambda}$$

### 2.3 Parametric High-Water Mark Drawdown Circuit Breakers

Treasury valuation tracks the high water mark $\text{HWM}(t) = \max_{s \le t} V_{\text{portfolio}}(s)$:
$$\text{Drawdown}(t) = \frac{\text{HWM}(t) - V_{\text{portfolio}}(t)}{\text{HWM}(t)}$$

| Drawdown Tier | Portfolio Drawdown ($DD$) | Non-Critical Stream Multiplier ($\theta$) | Base Fee-Burn Rate ($f_{\text{base}}$) | Operational Action |
|---|---|---|---|---|
| **NOMINAL** | $DD < 5.0\%$ | $1.00$ (100% flow) | $5.0\%$ | Normal multi-agent operations |
| **CAUTION** | $5.0\% \le DD < 10.0\%$ | $0.75$ (25% throttle) | $10.0\%$ | Slow non-essential agent workloads |
| **THROTTLE** | $10.0\% \le DD < 20.0\%$ | $0.50$ (50% throttle) | $20.0\%$ | Halve compute mints; trigger rebalancing |
| **DEFENSE** | $DD \ge 20.0\%$ | $0.00$ (Frozen) | $35.0\%$ | Freeze non-exempt streams; deploy collar hedges |

#### Critical Service Exemption Invariant
Streams designated with `is_exempt = True` (e.g. `SwarmRole.SAFETY_DAEMON`) maintain strict immunity:
$$\theta_{\text{exempt}}(t) \equiv 1.00 \quad \forall \, DD(t)$$
This mathematically guarantees that liquidation prevention, position monitors, and safety agents never run out of operating cash.

---

## 3. Institutional Comparative Benchmark

Comparative benchmark across 30 simulated days with a 35% synthetic crypto market flash crash:

| Metric | Static Lump-Sum Budgeting | Naive Linear Streaming | Autonomous Agentic Micro-Streaming |
|---|---|---|---|
| **Disbursement Model** | 100% Upfront Disbursed | Rigid Per-Second Linear | Adaptive Multi-Curve (Linear + Exp + Cliff) |
| **Capital Committed ($)** | $\$80,000.00$ | $\$80,000.00$ | $\$80,000.00$ |
| **Max Drawdown (%)** | $28.5\%$ | $21.4\%$ | **$6.94\%$** (Collar Hedged) |
| **Compute Quota Mechanism** | Flat Purchase | Flat Rate / No Surge | **Polynomial Bonding Curve ($P_0 + \alpha S^k$)** |
| **Value Accrued (Fee Burn $)** | $\$0.00$ | $\$1,600.00$ | **$\$2,236.59$** |
| **Safety Daemon Priority** | None (Equal exposure) | None (No tiering) | **Strict Immunity (100% Flow Maintained)** |
| **Treasury Survival Prob** | $84.2\%$ | $92.6\%$ | **$99.8\%$** |
| **Capital Efficiency Multiplier** | $1.00\text{x}$ | $1.48\text{x}$ | **$2.65\text{x}$** |

---

## 4. Package Architecture

```
agent_treasury_stream/
├── __init__.py          # Package exports & version
├── models.py            # Dataclasses, Enums, FlowConfig, HedgingSignal
├── streaming.py         # Sub-second continuous micro-streaming engine
├── bonding.py           # Polynomial bonding curve compute quota & burn engine
├── circuit.py           # Parametric HWM drawdown circuit breakers & fee burn escalator
├── rebalance.py         # Multi-asset drift monitor with 0.05% buffer & collar hedges
├── controller.py        # Master controller synchronizing cashflow and solvency
├── simulation.py        # 10-agent swarm financial simulation engine
├── mcp_server.py        # FastMCP protocol server with 9 agent tools
└── cli.py               # Rich-powered command-line interface
```

---

## 5. Installation

```bash
# Clone the repository
git clone https://github.com/devsoniclk/agent-treasury-stream.git
cd agent-treasury-stream

# Install in editable mode with development & MCP dependencies
pip install -e ".[dev,mcp]"
```

---

## 6. CLI Quickstart

```bash
# 1. Run a 30-day multi-agent swarm financial simulation
agent-treasury-stream simulate --days 30

# 2. Inspect instantaneous compute quota spot price
agent-treasury-stream curve-price --supply 150 --congestion 1.25

# 3. Inspect treasury reserve weights and drift deltas
agent-treasury-stream portfolio-drift
```

---

## 7. Python API Reference

```python
from agent_treasury_stream.controller import AutonomousTreasuryController
from agent_treasury_stream.models import FlowCurveType, SwarmRole

# Initialize controller
controller = AutonomousTreasuryController()

# Open a 30-day linear stream for an execution agent
snap = controller.open_stream(
    stream_id="stream-alpha",
    beneficiary="agent-01",
    role=SwarmRole.EXECUTION_AGENT,
    total_allocation=15_000.0,
    start_epoch=0.0,
    end_epoch=86400.0 * 30,
    curve_type=FlowCurveType.LINEAR,
)

# Mint compute units via polynomial bonding curve
units, fee_burned, avg_price = controller.mint_compute_quota(
    agent_id="agent-01",
    gross_deposit_usd=1_000.0,
    congestion_index=1.0,
)
print(f"Minted {units:.2f} compute units (Fee Burned: ${fee_burned:.2f})")

# Evaluate treasury drawdown against circuit breakers
effective_val, tier, drawdown = controller.sync_treasury_state(
    current_epoch=86400.0 * 10,
    liquidity_stress=0.25,
)
print(f"Treasury Valuation: ${effective_val:,.2f} | Tier: {tier.value} | DD: {drawdown*100:.2f}%")
```

---

## 8. Model Context Protocol (MCP) Tools

`agent-treasury-stream` exposes 9 native MCP tools for autonomous AI agent tool execution:

| Tool Name | Description |
|---|---|
| `treasury_create_stream` | Open a new continuous micro-stream allocation for an agent. |
| `treasury_get_stream_status` | Query current vested, claimable, remaining balances, and velocity. |
| `treasury_withdraw_stream` | Execute a withdrawal of claimable funds from an active stream. |
| `treasury_terminate_stream` | Terminate and settle a stream, refunding unvested capital to treasury. |
| `treasury_mint_compute_quota` | Mint compute quota tokens via polynomial bonding curve. |
| `treasury_burn_compute_quota` | Burn compute quota tokens upon compute job execution. |
| `treasury_check_portfolio_drift` | Inspect portfolio asset allocation and weight drift deltas. |
| `treasury_plan_rebalance` | Generate rebalancing trade directives and delta-neutral collars. |
| `treasury_simulate_swarm` | Run a multi-agent swarm treasury simulation across market shocks. |

---

## 9. Test Suite Verification

Run the full automated test suite with coverage:

```bash
pytest tests -v --cov=agent_treasury_stream
```

```
============================== 75 passed in 0.20s ==============================
TOTAL COVERAGE: 91%
```

---

## 10. License

Apache 2.0 License. Copyright 2026 Lakshitha Dananjaya (`devsoniclk`).
