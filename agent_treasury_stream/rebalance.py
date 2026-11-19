"""Multi-asset treasury rebalancing and delta-neutral risk control."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from agent_treasury_stream.models import (
    HedgingSignal,
    ReserveHolding,
)


class TreasuryRebalancer:
    """Monitors asset weight deviations and generates pipeline execution directives."""

    def __init__(
        self,
        holdings: Optional[Dict[str, ReserveHolding]] = None,
        drift_band_pct: float = 0.05,
        execution_buffer_pct: float = 0.0005,  # 0.05% buffer for orderbook crossing
    ) -> None:
        self.holdings: Dict[str, ReserveHolding] = holdings or {}
        self.drift_band_pct = drift_band_pct
        self.execution_buffer_pct = execution_buffer_pct
        self.signal_ledger: List[HedgingSignal] = []

    def set_holding(
        self,
        ticker: str,
        units: float,
        unit_price_usd: float,
        target_weight: float,
        is_hedged: bool = False,
    ) -> None:
        """Registers or updates a reserve holding."""
        if target_weight < 0.0:
            raise ValueError("Target weight cannot be negative")
        self.holdings[ticker] = ReserveHolding(
            ticker=ticker,
            units=units,
            unit_price_usd=unit_price_usd,
            target_weight=target_weight,
            is_hedged=is_hedged,
        )

    def refresh_price(self, ticker: str, price_usd: float) -> None:
        """Updates market valuation for a holding."""
        if ticker not in self.holdings:
            raise KeyError(f"Holding '{ticker}' not found")
        if price_usd <= 0.0:
            raise ValueError("Price must be strictly positive")
        self.holdings[ticker].unit_price_usd = price_usd

    def get_portfolio_usd_value(self) -> float:
        """Calculates aggregate USD value across all assets."""
        return sum(h.total_usd_value for h in self.holdings.values())

    def recalculate_weights(self) -> Dict[str, float]:
        """Recalculates current asset weights."""
        total = self.get_portfolio_usd_value()
        weights: Dict[str, float] = {}
        for ticker, h in self.holdings.items():
            h.current_weight = (h.total_usd_value / total) if total > 0.0 else 0.0
            weights[ticker] = h.current_weight
        return weights

    def compute_drift_deltas(self) -> Dict[str, float]:
        """Calculates absolute difference between current and target weights."""
        self.recalculate_weights()
        return {t: abs(h.current_weight - h.target_weight) for t, h in self.holdings.items()}

    def inspect_rebalance_triggers(
        self,
        band_pct: Optional[float] = None,
    ) -> Tuple[bool, str, float]:
        """Checks if any asset drift exceeds permissible bounds."""
        limit = band_pct if band_pct is not None else self.drift_band_pct
        drifts = self.compute_drift_deltas()
        if not drifts:
            return False, "", 0.0

        dominant_ticker = max(drifts.keys(), key=lambda k: drifts[k])
        max_drift = drifts[dominant_ticker]
        return max_drift >= limit, dominant_ticker, max_drift

    def plan_rebalance_orders(
        self,
        current_epoch: float,
        band_pct: Optional[float] = None,
        overlay_collar_hedges: bool = False,
    ) -> List[HedgingSignal]:
        """Generates trade directives to bring portfolio back to target allocations."""
        limit = band_pct if band_pct is not None else self.drift_band_pct
        needs_rebalance, _, _ = self.inspect_rebalance_triggers(limit)

        directives: List[HedgingSignal] = []
        if not needs_rebalance and not overlay_collar_hedges:
            return directives

        total_value = self.get_portfolio_usd_value()

        if needs_rebalance:
            for ticker, h in self.holdings.items():
                target_value = h.target_weight * total_value
                diff = target_value - h.total_usd_value
                drift = abs(h.current_weight - h.target_weight)

                if drift < (limit * 0.5):
                    continue

                if diff < 0.0:
                    # Trim overweight asset
                    qty = abs(diff) / h.unit_price_usd
                    entry = h.unit_price_usd * (1.0 - self.execution_buffer_pct)
                    directives.append(
                        HedgingSignal(
                            instrument=ticker,
                            direction="SELL",
                            target_entry=entry,
                            stop_boundary=h.unit_price_usd * 1.05,
                            profit_boundary=h.unit_price_usd * 0.90,
                            leverage=1.0,
                            expected_rr=2.0,
                            allocation_size=qty,
                            epoch=current_epoch,
                            memo=f"Trim overweight asset ({drift*100:.1f}% drift) to target {h.target_weight*100:.1f}%",
                        )
                    )
                elif diff > 0.0:
                    # Accumulate underweight asset
                    qty = diff / h.unit_price_usd
                    entry = h.unit_price_usd * (1.0 + self.execution_buffer_pct)
                    directives.append(
                        HedgingSignal(
                            instrument=ticker,
                            direction="BUY",
                            target_entry=entry,
                            stop_boundary=h.unit_price_usd * 0.95,
                            profit_boundary=h.unit_price_usd * 1.10,
                            leverage=1.0,
                            expected_rr=2.0,
                            allocation_size=qty,
                            epoch=current_epoch,
                            memo=f"Accumulate underweight asset ({drift*100:.1f}% drift) to target {h.target_weight*100:.1f}%",
                        )
                    )

        if overlay_collar_hedges:
            for ticker, h in self.holdings.items():
                if ticker in ("ETH", "SOL") and not h.is_hedged:
                    entry = h.unit_price_usd * (1.0 - self.execution_buffer_pct)
                    directives.append(
                        HedgingSignal(
                            instrument=f"{ticker}-PERP",
                            direction="HEDGE_SHORT",
                            target_entry=entry,
                            stop_boundary=h.unit_price_usd * 1.04,
                            profit_boundary=h.unit_price_usd * 0.92,
                            leverage=1.0,
                            expected_rr=2.0,
                            allocation_size=h.units,
                            epoch=current_epoch,
                            memo=f"Delta-neutral hedge overlay on {ticker} collateral",
                        )
                    )

        return directives

    def record_execution(self, signal: HedgingSignal) -> None:
        """Applies simulated execution of a rebalance signal to balances."""
        base_ticker = signal.instrument.replace("-PERP", "")
        if base_ticker not in self.holdings:
            return

        h = self.holdings[base_ticker]
        if signal.direction == "SELL":
            h.units = max(0.0, h.units - signal.allocation_size)
            if "USDC" in self.holdings:
                self.holdings["USDC"].units += signal.allocation_size * signal.target_entry
        elif signal.direction == "BUY":
            h.units += signal.allocation_size
            if "USDC" in self.holdings:
                cost = signal.allocation_size * signal.target_entry
                self.holdings["USDC"].units = max(0.0, self.holdings["USDC"].units - cost)
        elif signal.direction == "HEDGE_SHORT":
            h.is_hedged = True

        self.signal_ledger.append(signal)
        self.recalculate_weights()
