"""Unified controller coordinating agent treasury streaming and risk management."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from agent_treasury_stream.models import (
    FlowConfig,
    FlowCurveType,
    FlowSnapshot,
    HedgingSignal,
    ReserveHolding,
    SafetyBreakerSnapshot,
    SwarmRole,
    VolatilityTier,
)
from agent_treasury_stream.streaming import FlowStreamEngine
from agent_treasury_stream.bonding import ComputeBondingEngine
from agent_treasury_stream.circuit import ParametricSafetyBreaker
from agent_treasury_stream.rebalance import TreasuryRebalancer


class AutonomousTreasuryController:
    """Master controller managing streaming allocations, compute bonding, and solvency."""

    def __init__(
        self,
        initial_holdings: Optional[Dict[str, ReserveHolding]] = None,
        nominal_burn_fee: float = 0.05,
        execution_buffer_pct: float = 0.0005,
    ) -> None:
        if initial_holdings is None:
            initial_holdings = {
                "USDC": ReserveHolding(ticker="USDC", units=500_000.0, unit_price_usd=1.0, target_weight=0.50),
                "ETH": ReserveHolding(ticker="ETH", units=80.0, unit_price_usd=2500.0, target_weight=0.20),
                "SOL": ReserveHolding(ticker="SOL", units=1000.0, unit_price_usd=150.0, target_weight=0.15),
                "HLP": ReserveHolding(ticker="HLP", units=150_000.0, unit_price_usd=1.0, target_weight=0.15),
            }

        self.stream_engine = FlowStreamEngine()
        self.bonding_engine = ComputeBondingEngine()
        self.rebalancer = TreasuryRebalancer(
            holdings=initial_holdings,
            execution_buffer_pct=execution_buffer_pct,
        )
        self.safety_breaker = ParametricSafetyBreaker(
            baseline_capital=self.rebalancer.get_portfolio_usd_value(),
            nominal_burn_fee=nominal_burn_fee,
        )
        self.signals_emitted: List[HedgingSignal] = []

    def open_stream(
        self,
        stream_id: str,
        beneficiary: str,
        role: SwarmRole,
        total_allocation: float,
        start_epoch: float,
        end_epoch: float,
        curve_type: FlowCurveType = FlowCurveType.LINEAR,
        exponent: float = 1.0,
        cliff_epoch: float = 0.0,
        cliff_amount: float = 0.0,
        is_exempt: bool = False,
    ) -> FlowSnapshot:
        """Opens a new streaming allocation backed by treasury USDC reserves."""
        usdc = self.rebalancer.holdings.get("USDC")
        free_usdc = usdc.units if usdc else 0.0

        if free_usdc < total_allocation:
            raise ValueError(f"Insolvent: free USDC (${free_usdc:,.2f}) cannot cover allocation (${total_allocation:,.2f})")

        if usdc is not None:
            usdc.units -= total_allocation

        cfg = FlowConfig(
            stream_id=stream_id,
            funder="TREASURY_VAULT",
            beneficiary=beneficiary,
            role=role,
            total_allocation=total_allocation,
            start_epoch=start_epoch,
            end_epoch=end_epoch,
            curve_type=curve_type,
            exponent=exponent,
            cliff_epoch=cliff_epoch,
            cliff_amount=cliff_amount,
            is_exempt=is_exempt,
        )
        return self.stream_engine.register_stream(cfg)

    def mint_compute_quota(
        self,
        agent_id: str,
        gross_deposit_usd: float,
        congestion_index: float = 1.0,
        slippage_cap_pct: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """Mints compute quota tokens via bonding curve with circuit breaker fee escalation."""
        current_burn = self.safety_breaker.snapshot.burn_fee_rate
        return self.bonding_engine.mint_quota(
            agent_id=agent_id,
            gross_deposit_usd=gross_deposit_usd,
            slippage_cap_pct=slippage_cap_pct,
            congestion_index=congestion_index,
            fee_burn_override=current_burn,
        )

    def sync_treasury_state(
        self,
        current_epoch: float,
        liquidity_stress: float = 0.0,
    ) -> Tuple[float, VolatilityTier, float]:
        """
        Updates portfolio metrics, audits solvency, applies throttle multipliers.
        Returns: (effective_capital, volatility_tier, active_drawdown_pct)
        """
        holdings_value = self.rebalancer.get_portfolio_usd_value()
        outstanding_liabilities = self.stream_engine.calculate_total_outstanding_liabilities(current_epoch)
        effective_valuation = holdings_value + outstanding_liabilities

        snap = self.safety_breaker.evaluate_valuation(
            current_valuation=effective_valuation,
            liquidity_stress_factor=liquidity_stress,
        )
        self.safety_breaker.apply_to_engine(self.stream_engine, current_epoch)
        return effective_valuation, snap.tier, snap.active_drawdown_pct
