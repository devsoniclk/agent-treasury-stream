"""Continuous streaming engine for autonomous agents."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from agent_treasury_stream.models import (
    FlowConfig,
    FlowCurveType,
    FlowSnapshot,
    StreamLifecycleState,
    SwarmRole,
)


class FlowStreamEngine:
    """Manages continuous sub-second streaming disbursements to swarm agents."""

    def __init__(self) -> None:
        self.registry: Dict[str, FlowSnapshot] = {}
        self._vested_ledger: Dict[str, float] = {}
        self._cliff_disbursed: Dict[str, bool] = {}

    def register_stream(self, config: FlowConfig) -> FlowSnapshot:
        """Adds a new stream definition to the registry."""
        if config.stream_id in self.registry:
            raise ValueError(f"Stream '{config.stream_id}' is already registered")

        snapshot = FlowSnapshot(
            config=config,
            status=StreamLifecycleState.ACTIVE,
            withdrawn=0.0,
            last_checkpoint=config.start_epoch,
            throttle_rate=1.0,
        )
        self.registry[config.stream_id] = snapshot
        self._vested_ledger[config.stream_id] = 0.0
        self._cliff_disbursed[config.stream_id] = False
        return snapshot

    def _sync_stream_progress(self, stream_id: str, current_epoch: float) -> None:
        """Updates internal vested totals up to the given epoch."""
        snap = self.registry[stream_id]
        cfg = snap.config

        if current_epoch <= snap.last_checkpoint:
            return

        if snap.status != StreamLifecycleState.ACTIVE:
            snap.last_checkpoint = current_epoch
            return

        # Check cliff unlock
        if cfg.cliff_epoch > 0.0 and current_epoch < cfg.cliff_epoch:
            snap.last_checkpoint = current_epoch
            return

        if cfg.cliff_epoch > 0.0 and not self._cliff_disbursed[stream_id]:
            self._vested_ledger[stream_id] += cfg.cliff_amount
            self._cliff_disbursed[stream_id] = True

        t_start = max(snap.last_checkpoint, cfg.start_epoch)
        t_end = min(current_epoch, cfg.end_epoch)

        if t_end > t_start:
            total_duration = cfg.end_epoch - cfg.start_epoch
            distributable = cfg.total_allocation - cfg.cliff_amount

            if cfg.curve_type in (FlowCurveType.LINEAR, FlowCurveType.CLIFF):
                rate = distributable / total_duration
                accrued = rate * (t_end - t_start) * snap.throttle_rate
            elif cfg.curve_type == FlowCurveType.EXPONENTIAL:
                gamma = cfg.exponent
                p0 = max(0.0, min(1.0, (t_start - cfg.start_epoch) / total_duration))
                p1 = max(0.0, min(1.0, (t_end - cfg.start_epoch) / total_duration))
                accrued = distributable * ((p1 ** gamma) - (p0 ** gamma)) * snap.throttle_rate
            else:
                rate = distributable / total_duration
                accrued = rate * (t_end - t_start) * snap.throttle_rate

            self._vested_ledger[stream_id] += accrued

        # Cap total vested at allocation ceiling
        if self._vested_ledger[stream_id] > cfg.total_allocation:
            self._vested_ledger[stream_id] = cfg.total_allocation

        snap.last_checkpoint = current_epoch

        if current_epoch >= cfg.end_epoch and self._vested_ledger[stream_id] >= cfg.total_allocation:
            snap.status = StreamLifecycleState.COMPLETED

    def get_vested_balance(self, stream_id: str, current_epoch: float) -> float:
        """Calculates total cumulative vested capital at current epoch."""
        if stream_id not in self.registry:
            raise KeyError(f"Unknown stream '{stream_id}'")
        self._sync_stream_progress(stream_id, current_epoch)
        return self._vested_ledger[stream_id]

    def get_claimable_amount(self, stream_id: str, current_epoch: float) -> float:
        """Returns claimable balance available for agent withdrawal."""
        vested = self.get_vested_balance(stream_id, current_epoch)
        snap = self.registry[stream_id]
        return max(0.0, vested - snap.withdrawn)

    def get_remaining_liability(self, stream_id: str, current_epoch: float) -> float:
        """Returns unvested treasury obligations remaining on this stream."""
        vested = self.get_vested_balance(stream_id, current_epoch)
        snap = self.registry[stream_id]
        return max(0.0, snap.config.total_allocation - vested)

    def execute_withdrawal(self, stream_id: str, requested_amount: float, current_epoch: float) -> float:
        """Withdraws claimable capital for the beneficiary."""
        if requested_amount <= 0.0:
            raise ValueError("Withdrawal amount must be strictly positive")

        claimable = self.get_claimable_amount(stream_id, current_epoch)
        if requested_amount > claimable + 1e-9:
            raise ValueError(f"Requested {requested_amount:.4f} exceeds claimable balance {claimable:.4f}")

        actual_payout = min(requested_amount, claimable)
        self.registry[stream_id].withdrawn += actual_payout
        return actual_payout

    def pause_flow(self, stream_id: str, current_epoch: float) -> None:
        """Pauses vesting accumulation on an active stream."""
        if stream_id not in self.registry:
            raise KeyError(f"Unknown stream '{stream_id}'")
        self._sync_stream_progress(stream_id, current_epoch)
        self.registry[stream_id].status = StreamLifecycleState.PAUSED

    def resume_flow(self, stream_id: str, current_epoch: float) -> None:
        """Resumes a previously paused stream."""
        if stream_id not in self.registry:
            raise KeyError(f"Unknown stream '{stream_id}'")
        snap = self.registry[stream_id]
        if snap.status == StreamLifecycleState.PAUSED:
            snap.last_checkpoint = current_epoch
            snap.status = StreamLifecycleState.ACTIVE

    def terminate_and_settle(self, stream_id: str, current_epoch: float) -> Tuple[float, float]:
        """
        Cancels stream and performs exact conservation settlement.
        Returns: (beneficiary_claim, treasury_refund)
        """
        if stream_id not in self.registry:
            raise KeyError(f"Unknown stream '{stream_id}'")
        snap = self.registry[stream_id]
        if snap.status in (StreamLifecycleState.CANCELLED, StreamLifecycleState.COMPLETED):
            return 0.0, 0.0

        self._sync_stream_progress(stream_id, current_epoch)
        vested = self._vested_ledger[stream_id]
        claim = max(0.0, vested - snap.withdrawn)
        refund = max(0.0, snap.config.total_allocation - vested)

        snap.withdrawn += claim
        snap.status = StreamLifecycleState.CANCELLED
        return claim, refund

    def set_throttle(self, stream_id: str, throttle_rate: float, current_epoch: float) -> None:
        """Applies dynamic flow throttling coefficient in range [0.0, 1.0]."""
        if stream_id not in self.registry:
            raise KeyError(f"Unknown stream '{stream_id}'")
        if throttle_rate < 0.0 or throttle_rate > 1.0:
            raise ValueError("Throttle rate must be bounded between 0.0 and 1.0")

        snap = self.registry[stream_id]
        if snap.config.is_exempt:
            snap.throttle_rate = 1.0
            return

        self._sync_stream_progress(stream_id, current_epoch)
        snap.throttle_rate = throttle_rate

    def get_instantaneous_velocity(self, stream_id: str, current_epoch: float) -> float:
        """Calculates instantaneous burn velocity in USD per second."""
        if stream_id not in self.registry:
            raise KeyError(f"Unknown stream '{stream_id}'")
        snap = self.registry[stream_id]
        if snap.status != StreamLifecycleState.ACTIVE:
            return 0.0

        cfg = snap.config
        if current_epoch < cfg.start_epoch or current_epoch >= cfg.end_epoch:
            return 0.0
        if cfg.cliff_epoch > 0.0 and current_epoch < cfg.cliff_epoch:
            return 0.0

        duration = cfg.end_epoch - cfg.start_epoch
        distributable = cfg.total_allocation - cfg.cliff_amount

        if cfg.curve_type in (FlowCurveType.LINEAR, FlowCurveType.CLIFF):
            return (distributable / duration) * snap.throttle_rate
        elif cfg.curve_type == FlowCurveType.EXPONENTIAL:
            gamma = cfg.exponent
            progress = max(0.0, min(1.0, (current_epoch - cfg.start_epoch) / duration))
            if progress <= 0.0:
                return 0.0
            velocity = (distributable * gamma / duration) * (progress ** (gamma - 1.0))
            return velocity * snap.throttle_rate
        return 0.0

    def calculate_aggregate_burn_rate(self, current_epoch: float) -> float:
        """Returns total current cashflow velocity across all active streams."""
        return sum(self.get_instantaneous_velocity(sid, current_epoch) for sid in self.registry)

    def calculate_total_outstanding_liabilities(self, current_epoch: float) -> float:
        """Returns aggregate unvested commitments across all active/paused streams."""
        total = 0.0
        for sid, snap in self.registry.items():
            if snap.status in (StreamLifecycleState.ACTIVE, StreamLifecycleState.PAUSED):
                total += self.get_remaining_liability(sid, current_epoch)
        return total

    def check_solvency_runway(
        self,
        liquid_reserves_usd: float,
        horizon_seconds: float = 86400.0 * 7,
        current_epoch: float = 0.0
    ) -> Tuple[bool, float, float]:
        """
        Verifies if liquid treasury reserves cover expected burn over horizon.
        Returns: (is_solvent, required_reserves, coverage_ratio)
        """
        active_velocity = self.calculate_aggregate_burn_rate(current_epoch)
        required = active_velocity * horizon_seconds
        ratio = liquid_reserves_usd / (required + 1e-9)
        return liquid_reserves_usd >= required, required, ratio
