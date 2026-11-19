"""Polynomial bonding curve engine for autonomous agent compute quotas."""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple
from agent_treasury_stream.models import (
    BondingCurveParams,
    SwarmAllocationRecord,
)


class ComputeBondingEngine:
    """Manages dynamic compute token pricing, reserves, and burn mechanics."""

    def __init__(self, params: Optional[BondingCurveParams] = None) -> None:
        self.params = params or BondingCurveParams()
        self.circulating_supply: float = 0.0
        self.treasury_vault_usd: float = 0.0
        self.cumulative_fee_burned_usd: float = 0.0
        self.cumulative_tokens_burned: float = 0.0
        self.allocations: Dict[str, SwarmAllocationRecord] = {}

    def get_spot_unit_price(
        self,
        supply: Optional[float] = None,
        congestion_index: float = 1.0,
    ) -> float:
        """Calculates instantaneous spot price for one compute unit."""
        s = max(0.0, self.circulating_supply if supply is None else supply)
        p0 = self.params.base_unit_price
        alpha = self.params.sensitivity_alpha
        k = self.params.exponent_k
        raw_price = p0 + alpha * (s ** k)
        return raw_price * max(1.0, congestion_index)

    def calculate_reserve_integral(self, supply: float) -> float:
        """Analytically computes total reserve required for a given supply level."""
        s = max(0.0, supply)
        p0 = self.params.base_unit_price
        alpha = self.params.sensitivity_alpha
        k = self.params.exponent_k
        return p0 * s + (alpha / (k + 1.0)) * (s ** (k + 1.0))

    def estimate_mint_cost(
        self,
        additional_units: float,
        congestion_index: float = 1.0,
    ) -> float:
        """Calculates gross reserve currency needed to mint additional units."""
        if additional_units <= 0.0:
            return 0.0
        r_start = self.calculate_reserve_integral(self.circulating_supply)
        r_end = self.calculate_reserve_integral(self.circulating_supply + additional_units)
        return (r_end - r_start) * max(1.0, congestion_index)

    def solve_units_for_deposit(
        self,
        net_deposit_usd: float,
        congestion_index: float = 1.0,
    ) -> float:
        """Uses Newton-Raphson to solve for units yielded by net reserve deposit."""
        if net_deposit_usd <= 0.0:
            return 0.0

        effective_delta = net_deposit_usd / max(1.0, congestion_index)
        s0 = self.circulating_supply
        r0 = self.calculate_reserve_integral(s0)
        target_r = r0 + effective_delta

        # Initial estimate based on spot price
        p_current = self.get_spot_unit_price(s0)
        delta_s = effective_delta / p_current

        for _ in range(30):
            cand_s = s0 + delta_s
            err = self.calculate_reserve_integral(cand_s) - target_r
            if abs(err) < 1e-10:
                break
            slope = self.get_spot_unit_price(cand_s, congestion_index=1.0)
            if slope <= 1e-12:
                break
            delta_s -= err / slope
            if delta_s < 0.0:
                delta_s = 1e-6

        return max(0.0, delta_s)

    def mint_quota(
        self,
        agent_id: str,
        gross_deposit_usd: float,
        slippage_cap_pct: Optional[float] = None,
        congestion_index: float = 1.0,
        fee_burn_override: Optional[float] = None,
    ) -> Tuple[float, float, float]:
        """
        Mints compute quota for an agent.
        Deducts fee burn, deposits net capital to vault, and credits units.
        Returns: (units_minted, fee_burned_usd, average_fill_price)
        """
        if gross_deposit_usd <= 0.0:
            raise ValueError("Gross deposit must be positive")

        burn_pct = fee_burn_override if fee_burn_override is not None else self.params.nominal_fee_burn_pct
        burn_pct = max(0.0, min(0.90, burn_pct))

        fee_burned = gross_deposit_usd * burn_pct
        net_capital = gross_deposit_usd - fee_burned

        spot_prior = self.get_spot_unit_price(congestion_index=congestion_index)
        units = self.solve_units_for_deposit(net_capital, congestion_index=congestion_index)

        if units <= 0.0:
            raise ValueError("Deposit insufficient to mint compute units")

        avg_price = net_capital / units

        if slippage_cap_pct is not None and avg_price > spot_prior * (1.0 + slippage_cap_pct):
            raise ValueError(f"Slippage limit violated: avg price {avg_price:.4f} > limit {spot_prior * (1.0 + slippage_cap_pct):.4f}")

        if self.circulating_supply + units > self.params.max_quota_supply:
            raise ValueError("Minting would exceed max supply")

        self.circulating_supply += units
        self.treasury_vault_usd += net_capital
        self.cumulative_fee_burned_usd += fee_burned

        if agent_id not in self.allocations:
            self.allocations[agent_id] = SwarmAllocationRecord(
                agent_id=agent_id,
                units_minted=0.0,
                reserve_spent_usd=0.0,
                units_burned=0.0,
                compute_cycles_used=0.0,
            )

        rec = self.allocations[agent_id]
        rec.units_minted += units
        rec.reserve_spent_usd += gross_deposit_usd

        return units, fee_burned, avg_price

    def consume_compute(
        self,
        agent_id: str,
        units_to_burn: float,
        cycles_per_unit: float = 1.0,
    ) -> float:
        """Consumes and permanently destroys compute units during agent inference."""
        if agent_id not in self.allocations:
            raise KeyError(f"No allocation for agent '{agent_id}'")
        if units_to_burn <= 0.0:
            raise ValueError("Burn units must be strictly positive")

        rec = self.allocations[agent_id]
        avail = rec.units_minted - rec.units_burned
        if units_to_burn > avail + 1e-9:
            raise ValueError(f"Insufficient compute quota: agent has {avail:.4f}, requested {units_to_burn:.4f}")

        burned = min(units_to_burn, avail)
        rec.units_burned += burned
        delivered = burned * cycles_per_unit
        rec.compute_cycles_used += delivered

        self.circulating_supply = max(0.0, self.circulating_supply - burned)
        self.cumulative_tokens_burned += burned
        return delivered

    def liquidate_surplus_quota(
        self,
        agent_id: str,
        units_to_redeem: float,
        protocol_exit_fee_pct: float = 0.02,
    ) -> Tuple[float, float]:
        """Refunds unconsumed compute units back into reserve cash."""
        if agent_id not in self.allocations:
            raise KeyError(f"No allocation for agent '{agent_id}'")
        if units_to_redeem <= 0.0:
            raise ValueError("Redeem units must be strictly positive")

        rec = self.allocations[agent_id]
        avail = rec.units_minted - rec.units_burned
        if units_to_redeem > avail + 1e-9:
            raise ValueError(f"Insufficient surplus quota: cannot redeem {units_to_redeem:.4f} > available {avail:.4f}")

        s1 = self.circulating_supply
        s0 = max(0.0, s1 - units_to_redeem)
        gross_refund = min(
            self.calculate_reserve_integral(s1) - self.calculate_reserve_integral(s0),
            self.treasury_vault_usd,
        )

        fee = gross_refund * protocol_exit_fee_pct
        net_refund = gross_refund - fee

        self.circulating_supply = s0
        self.treasury_vault_usd = max(0.0, self.treasury_vault_usd - gross_refund)
        self.cumulative_fee_burned_usd += fee
        rec.units_minted -= units_to_redeem

        return net_refund, fee
