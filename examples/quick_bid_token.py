"""Quick script to bid on a token ticker in the auction.

⚠️  EDIT THE CONFIGURATION BELOW BEFORE RUNNING!
"""

import json
import time
from datetime import datetime, timezone
import os

import example_utils

from hyperliquid.utils import constants

# ============================================================================
# CONFIGURATION - EDIT THESE VALUES!
# ============================================================================
TOKEN_NAME = os.getenv("TOKEN_SYMBOL", "PLACEHOLDER")  # ⚠️  CHANGE THIS: Token ticker (3-10 chars, uppercase)
SZ_DECIMALS = 2  # Size decimals (precision for trading, typically 0-8)
WEI_DECIMALS = 8  # Wei decimals (precision for on-chain, typically 5-8)
MAX_GAS = 14500000000000000  # ⚠️  Max gas in wei (14500 HYPE = 14500000000000000)
FULL_NAME = os.getenv("TOKEN_FULL_NAME", "PLACEHOLDER")  # ⚠️  CHANGE THIS: Full descriptive name
# ============================================================================


def main():
    print("=" * 60)
    print("QUICK TOKEN BID")
    print("=" * 60)
    print(f"\nToken: {TOKEN_NAME}")
    print(f"Full name: {FULL_NAME}")
    print(f"Size decimals: {SZ_DECIMALS}")
    print(f"Wei decimals: {WEI_DECIMALS}")
    print(f"Max gas: {MAX_GAS} ({MAX_GAS / 1e12:.2f} HYPE)")

    # Check auction status first
    address, info, exchange = example_utils.setup(constants.TESTNET_API_URL, skip_ws=True)

    print("\n" + "=" * 60)
    print("Checking Auction Status...")
    print("=" * 60)

    # Poll until auction is active
    POLL_INTERVAL = 5  # Check every 5 seconds
    AUTO_BID = True  # Set to False to require manual confirmation

    while True:
        auction_status = info.query_spot_deploy_auction_status(address)
        gas_auction = auction_status.get("gasAuction", {})
        current_gas = gas_auction.get("currentGas")

        if current_gas is None:
            # Check if auction hasn't started yet or has completed
            if gas_auction.get("startTimeSeconds"):
                start_utc = datetime.fromtimestamp(gas_auction["startTimeSeconds"], tz=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc < start_utc:
                    time_until = (start_utc - now_utc).total_seconds()
                    print(f"⏳ Auction hasn't started yet. Waiting... ({int(time_until)}s until start)")
                    time.sleep(min(POLL_INTERVAL, time_until))
                    continue
                else:
                    print("❌ Auction has completed. Wait for the next one.")
                    return
            else:
                print("⏳ Waiting for auction to start...")
                time.sleep(POLL_INTERVAL)
                continue
        else:
            # Auction is active! Check if price is acceptable
            start_gas = float(gas_auction.get("startGas", 0))
            current_gas_float = float(current_gas)
            max_gas_float = MAX_GAS / 1e12  # Convert to HYPE

            print(f"\nAuction Status:")
            print(f"  Start gas: {start_gas} HYPE")
            print(f"  Current gas: {current_gas_float} HYPE")
            print(f"  Your max gas: {max_gas_float} HYPE")

            if current_gas_float * 1e12 > MAX_GAS:
                print(f"\n⏳ Price too high ({current_gas_float:.2f} HYPE > {max_gas_float:.2f} HYPE)")
                print(f"   Waiting for price to drop... (checking every {POLL_INTERVAL}s)")
                time.sleep(POLL_INTERVAL)
                continue
            else:
                # Price is acceptable!
                print(f"\n✅ Price is acceptable! ({current_gas_float:.2f} HYPE <= {max_gas_float:.2f} HYPE)")
                break

    # Get final values after breaking out of loop
    auction_status = info.query_spot_deploy_auction_status(address)
    gas_auction = auction_status.get("gasAuction", {})
    current_gas = gas_auction.get("currentGas")
    current_gas_float = float(current_gas)
    max_gas_float = MAX_GAS / 1e12

    print("\n" + "=" * 60)
    print("✅ Auction is ACTIVE - Ready to Bid!")
    print("=" * 60)
    print(f"\nYou will bid on ticker: {TOKEN_NAME}")
    print(f"Max gas: {max_gas_float} HYPE")
    print(f"Current gas: {current_gas_float} HYPE")

    if AUTO_BID:
        print("\n⚠️  AUTO-BID ENABLED - Bidding automatically in 3 seconds...")
        print("   (Press Ctrl+C to cancel)")
        time.sleep(3)
    else:
        print("\n⚠️  This will participate in the auction NOW!")
        response = input("Proceed with bid? (yes/no): ")
        if response.lower() != "yes":
            print("Cancelled.")
            return

    print("\nSubmitting bid...")
    result = exchange.spot_deploy_register_token(
        token_name=TOKEN_NAME,
        sz_decimals=SZ_DECIMALS,
        wei_decimals=WEI_DECIMALS,
        max_gas=MAX_GAS,
        full_name=FULL_NAME,
    )

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result, indent=2))

    if result["status"] == "ok":
        token_index = result["response"]["data"]
        print(f"\n✅ SUCCESS! Token registered!")
        print(f"   Token index: {token_index}")
        print(f"   Token name: {TOKEN_NAME}")
        print("\n⚠️  IMPORTANT: Save this token index ({})!".format(token_index))
        print("   You'll need it for genesis and other steps.")
    else:
        print("\n❌ Bid failed. Check the error above.")


if __name__ == "__main__":
    main()
    

