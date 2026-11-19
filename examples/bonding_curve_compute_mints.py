"""Example: Polynomial bonding curve compute quota minting and burning."""

from agent_treasury_stream.bonding import ComputeBondingEngine


def main() -> None:
    print("=== Agent Compute Bonding Curve Engine Demo ===")
    bonding = ComputeBondingEngine()

    print(f"Initial Spot Price: ${bonding.get_spot_unit_price():.4f} USD")

    # 1. First agent mints with $1,000 USD
    agent_1 = "agent-researcher"
    units_1, fee_burned_1, avg_price_1 = bonding.mint_quota(agent_1, gross_deposit_usd=1_000.0)
    print(f"\n{agent_1} minted {units_1:,.2f} compute units.")
    print(f"Fee Burned: ${fee_burned_1:,.2f} | Avg Fill Price: ${avg_price_1:.4f} USD")
    print(f"New Spot Price: ${bonding.get_spot_unit_price():.4f} USD | Supply: {bonding.circulating_supply:,.2f}")

    # 2. Second agent mints during congestion (1.5x)
    agent_2 = "agent-trainer"
    units_2, fee_burned_2, avg_price_2 = bonding.mint_quota(
        agent_2, gross_deposit_usd=5_000.0, congestion_index=1.5
    )
    print(f"\n{agent_2} minted {units_2:,.2f} units during 1.5x congestion.")
    print(f"Fee Burned: ${fee_burned_2:,.2f} | Avg Fill Price: ${avg_price_2:.4f} USD")
    print(f"New Spot Price: ${bonding.get_spot_unit_price():.4f} USD | Supply: {bonding.circulating_supply:,.2f}")

    # 3. Agent 1 burns compute units for inference execution
    burned = bonding.burn_units(agent_1, units=50.0)
    print(f"\n{agent_1} burned {burned:,.2f} compute units for task execution.")
    print(f"Cumulative Tokens Burned: {bonding.cumulative_tokens_burned:,.2f}")
    print(f"Cumulative Fees Burned: ${bonding.cumulative_fee_burned_usd:,.2f} USD")


if __name__ == "__main__":
    main()
