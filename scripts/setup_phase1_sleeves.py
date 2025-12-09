#!/usr/bin/env python3
"""Generate Phase 1 sleeve configurations for Prometheus v2 backtesting.

This script generates the three core sleeves (H5, H21, H63) that will be used
for the initial backtest campaign. These sleeves differ only in assessment
horizon.

The sleeves are configuration objects (not database records) that get passed
to run_backtest_campaign.py.
"""

from prometheus.backtest.catalog import build_core_long_sleeves

# Strategy and market parameters
STRATEGY_ID = "US_CORE_LONG_EQ"
MARKET_ID = "US_EQ"

def main() -> None:
    """Generate and display Phase 1 sleeve configurations."""
    
    print("=" * 80)
    print("PHASE 1: Core Strategy Sleeve Configuration")
    print("=" * 80)
    print()
    
    print(f"Strategy ID: {STRATEGY_ID}")
    print(f"Market ID:   {MARKET_ID}")
    print(f"Description: Long-only US equity strategy on S&P 500 universe")
    print()
    
    # Generate the three sleeves
    sleeves = build_core_long_sleeves(
        strategy_id=STRATEGY_ID,
        market_id=MARKET_ID
    )
    
    print(f"Generated {len(sleeves)} sleeves:")
    print()
    
    for i, sleeve in enumerate(sleeves, 1):
        print(f"Sleeve {i}: {sleeve.sleeve_id}")
        print(f"  Strategy ID:             {sleeve.strategy_id}")
        print(f"  Market ID:               {sleeve.market_id}")
        print(f"  Universe ID:             {sleeve.universe_id}")
        print(f"  Portfolio ID:            {sleeve.portfolio_id}")
        print(f"  Assessment Strategy ID:  {sleeve.assessment_strategy_id}")
        print(f"  Assessment Horizon:      {sleeve.assessment_horizon_days} days")
        print(f"  Assessment Backend:      {sleeve.assessment_backend}")
        print()
    
    print("=" * 80)
    print("CLI Format for run_backtest_campaign.py")
    print("=" * 80)
    print()
    
    for sleeve in sleeves:
        # Format: sleeve_id:strategy_id:market_id:universe_id:portfolio_id:assessment_strategy_id:assessment_horizon_days
        cli_format = (
            f"{sleeve.sleeve_id}:"
            f"{sleeve.strategy_id}:"
            f"{sleeve.market_id}:"
            f"{sleeve.universe_id}:"
            f"{sleeve.portfolio_id}:"
            f"{sleeve.assessment_strategy_id}:"
            f"{sleeve.assessment_horizon_days}"
        )
        print(f"--sleeve {cli_format} \\")
    
    print()
    print("=" * 80)
    print("Example Backtest Command")
    print("=" * 80)
    print()
    print("python prometheus/scripts/run_backtest_campaign.py \\")
    print(f"  --market-id {MARKET_ID} \\")
    print("  --start 2014-01-01 \\")
    print("  --end 2014-03-31 \\")
    
    for sleeve in sleeves:
        cli_format = (
            f"{sleeve.sleeve_id}:"
            f"{sleeve.strategy_id}:"
            f"{sleeve.market_id}:"
            f"{sleeve.universe_id}:"
            f"{sleeve.portfolio_id}:"
            f"{sleeve.assessment_strategy_id}:"
            f"{sleeve.assessment_horizon_days}"
        )
        print(f"  --sleeve {cli_format} \\")
    
    print("  --initial-cash 1000000 \\")
    print("  --max-workers 3")
    print()


if __name__ == "__main__":
    main()
