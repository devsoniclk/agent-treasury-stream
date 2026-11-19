"""High water mark drawdown circuit breakers and liquidity defense."""

from __future__ import annotations

from typing import Optional, Tuple
from agent_treasury_stream.models import (
    SafetyBreakerSnapshot,
    VolatilityTier,
)
from agent_treasury_stream.streaming import FlowStreamEngine


class ParametricSafetyBreaker:
    """Monitors treasury capital preservation and throttles non-exempt agent streams."""

    def __init__(
        self,
        baseline_capital: float,
        caution_tier_pct: float = 0.05,
        throttle_tier_pct: float = 0.10,
        defense_tier_pct: float = 0.20,
        nominal_burn_fee: float = 0.05,
    ) -> None:
        if baseline_capital <= 0.0:
            raise ValueError("Baseline capital must be positive")

        self.peak_capital: float = baseline_capital
        self.caution_tier_pct = caution_tier_pct
        self.throttle_tier_pct = throttle_tier_pct
        self.defense_tier_pct = defense_tier_pct
        self.nominal_burn_fee = nominal_burn_fee

        self.snapshot = SafetyBreakerSnapshot(
            peak_valuation=self.peak_capital,
            active_drawdown_pct=0.0,
            tier=VolatilityTier.NOMINAL,
            payout_multiplier=1.0,
            burn_fee_rate=nominal_burn_fee,
            emergency_lockout=False,
        )

    def evaluate_valuation(
        self,
        current_valuation: float,
        liquidity_stress_factor: float = 0.0,
    ) -> SafetyBreakerSnapshot:
        """Evaluates drawdown against peak capital and updates defense status."""
        val = max(1e-6, current_valuation)
        if val > self.peak_capital:
            self.peak_capital = val

        drawdown = max(0.0, (self.peak_capital - val) / self.peak_capital)
        stress = max(0.0, min(1.0, liquidity_stress_factor))

        if drawdown >= self.defense_tier_pct:
            tier = VolatilityTier.DEFENSE
            multiplier = 0.0
            base_fee = 0.35
            lockout = True
        elif drawdown >= self.throttle_tier_pct:
            tier = VolatilityTier.THROTTLE
            multiplier = 0.50
            base_fee = 0.20
            lockout = False
        elif drawdown >= self.caution_tier_pct:
            tier = VolatilityTier.CAUTION
            multiplier = 0.75
            base_fee = 0.10
            lockout = False
        else:
            tier = VolatilityTier.NOMINAL
            multiplier = 1.0
            base_fee = self.nominal_burn_fee
            lockout = False

        escalated_burn = min(0.50, base_fee * (1.0 + 2.5 * stress))

        self.snapshot = SafetyBreakerSnapshot(
            peak_valuation=self.peak_capital,
            active_drawdown_pct=drawdown,
            tier=tier,
            payout_multiplier=multiplier,
            burn_fee_rate=escalated_burn,
            emergency_lockout=lockout,
        )
        return self.snapshot

    def apply_to_engine(self, engine: FlowStreamEngine, current_epoch: float) -> int:
        """Propagates throttling multiplier across all non-exempt streams in the engine."""
        throttled_total = 0
        mult = self.snapshot.payout_multiplier

        for sid, snap in engine.registry.items():
            if snap.config.is_exempt:
                engine.set_throttle(sid, 1.0, current_epoch)
            else:
                engine.set_throttle(sid, mult, current_epoch)
                if mult < 1.0:
                    throttled_total += 1

        return throttled_total

    def reset_peak(self, new_peak: Optional[float] = None) -> None:
        """Resets high water mark following intentional distributions or capital recalibrations."""
        if new_peak is not None:
            if new_peak <= 0.0:
                raise ValueError("New peak capital must be positive")
            self.peak_capital = new_peak
        self.snapshot.peak_valuation = self.peak_capital
        self.snapshot.active_drawdown_pct = 0.0
