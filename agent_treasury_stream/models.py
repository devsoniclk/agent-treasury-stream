"""Core data models and type definitions for agent treasury streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class FlowCurveType(str, Enum):
    """Vesting flow curves."""
    LINEAR = "LINEAR"
    EXPONENTIAL = "EXPONENTIAL"
    CLIFF = "CLIFF"


class StreamLifecycleState(str, Enum):
    """Lifecycle statuses for an active or closed stream."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class SwarmRole(str, Enum):
    """Recognized agent swarm operational roles."""
    SENTINEL = "SENTINEL"
    EXECUTION_AGENT = "EXECUTION_AGENT"
    RESEARCH_AGENT = "RESEARCH_AGENT"
    SAFETY_DAEMON = "SAFETY_DAEMON"
    GENERAL_WORKER = "GENERAL_WORKER"


class VolatilityTier(str, Enum):
    """Drawdown severity levels."""
    NOMINAL = "NOMINAL"       # Drawdown < 5%
    CAUTION = "CAUTION"       # 5% <= Drawdown < 10%
    THROTTLE = "THROTTLE"     # 10% <= Drawdown < 20%
    DEFENSE = "DEFENSE"       # Drawdown >= 20%


@dataclass
class FlowConfig:
    """Configuration parameter set for an individual agent stream."""
    stream_id: str
    funder: str
    beneficiary: str
    role: SwarmRole
    total_allocation: float
    start_epoch: float
    end_epoch: float
    curve_type: FlowCurveType = FlowCurveType.LINEAR
    exponent: float = 1.0
    cliff_epoch: float = 0.0
    cliff_amount: float = 0.0
    is_exempt: bool = False

    def __post_init__(self) -> None:
        if self.end_epoch <= self.start_epoch:
            raise ValueError(f"end_epoch ({self.end_epoch}) must exceed start_epoch ({self.start_epoch})")
        if self.total_allocation <= 0.0:
            raise ValueError("total_allocation must be positive")
        if self.cliff_amount < 0.0 or self.cliff_amount > self.total_allocation:
            raise ValueError("cliff_amount must be between 0 and total_allocation")
        if self.cliff_epoch > 0.0 and (self.cliff_epoch < self.start_epoch or self.cliff_epoch > self.end_epoch):
            raise ValueError("cliff_epoch must be between start and end epochs")


@dataclass
class FlowSnapshot:
    """State snapshot of an agent cashflow stream."""
    config: FlowConfig
    status: StreamLifecycleState = StreamLifecycleState.ACTIVE
    withdrawn: float = 0.0
    last_checkpoint: float = 0.0
    throttle_rate: float = 1.0


@dataclass
class ReserveHolding:
    """Balance and target weight for a treasury asset."""
    ticker: str
    units: float
    unit_price_usd: float
    target_weight: float
    current_weight: float = 0.0
    is_hedged: bool = False

    @property
    def total_usd_value(self) -> float:
        return self.units * self.unit_price_usd


@dataclass
class BondingCurveParams:
    """Parameters governing compute quota pricing."""
    base_unit_price: float = 1.0
    sensitivity_alpha: float = 0.005
    exponent_k: float = 2.0
    nominal_fee_burn_pct: float = 0.05
    max_quota_supply: float = 1_000_000.0


@dataclass
class SwarmAllocationRecord:
    """Audit record for compute quota minted and burned by an agent."""
    agent_id: str
    units_minted: float
    reserve_spent_usd: float
    units_burned: float = 0.0
    compute_cycles_used: float = 0.0


@dataclass
class SafetyBreakerSnapshot:
    """Health snapshot of treasury high water mark and circuit breakers."""
    peak_valuation: float
    active_drawdown_pct: float
    tier: VolatilityTier
    payout_multiplier: float
    burn_fee_rate: float
    emergency_lockout: bool


@dataclass
class HedgingSignal:
    """Standardized trading or hedging signal."""
    instrument: str
    direction: str
    target_entry: float
    stop_boundary: float
    profit_boundary: float
    leverage: float
    expected_rr: float
    allocation_size: float
    epoch: float
    memo: str

    def format_pipeline_directive(self) -> str:
        return (
            f"{self.instrument} | {self.direction} | {self.target_entry:.4f} | "
            f"{self.stop_boundary:.4f} | {self.profit_boundary:.4f} | "
            f"{self.leverage:.1f}x | {self.expected_rr:.2f} | {self.allocation_size:.2f}"
        )
