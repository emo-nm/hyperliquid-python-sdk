"""
Script to finalize EVM contract linking with HyperCore spot token.
This only performs the finalizeEvmContract action - assumes everything else is already set up.
"""
import json
import os
from pathlib import Path
from typing import Literal, TypedDict, Union

import requests
from dotenv import load_dotenv
from eth_account import Account
from eth_account.signers.local import LocalAccount

from hyperliquid.utils import constants
from hyperliquid.utils.signing import get_timestamp_ms, sign_l1_action

# Load environment variables from .env file
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


class CreateInputParams(TypedDict):
    nonce: int


class CreateInput(TypedDict):
    create: CreateInputParams


# According to docs: input can be:
# - {"create": {"nonce": number}} for EOA deployment
# - "firstStorageSlot" for first storage slot
# - "customStorageSlot" for slot at keccak256("HyperCore deployer")
FinalizeEvmContractInput = Union[Literal["firstStorageSlot"], Literal["customStorageSlot"], CreateInput]


class FinalizeEvmContractAction(TypedDict):
    type: Literal["finalizeEvmContract"]
    token: int
    input: FinalizeEvmContractInput


# Configuration
TOKEN = int(os.getenv("TOKEN_INDEX",'0'))  # Your token index
PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0xPRIVATE_KEY")  # From .env file or env var

# Storage slot options - set ONE of these:
# Option 1: Use first storage slot
USE_FIRST_STORAGE_SLOT = False

# Option 2: Use deploy nonce (if you deployed the contract)
USE_DEPLOY_NONCE = False
DEPLOY_NONCE = 0  # Set this to your contract's creation nonce

# Option 3: Use custom storage slot
# This uses the slot at keccak256("HyperCore deployer") which must store the finalizer address
USE_CUSTOM_STORAGE_SLOT = True

# Dry run mode
DRY_RUN = False  # Set to False to actually send

# API endpoint (testnet or mainnet)
USE_MAINNET = False
API_URL = constants.MAINNET_API_URL if USE_MAINNET else constants.TESTNET_API_URL


def main():
    print("="*80)
    print("FINALIZE EVM CONTRACT - HyperCore to HyperEVM Linking")
    print("="*80)
    
    # Validate configuration
    if PRIVATE_KEY == "0xPRIVATE_KEY":
        print("❌ ERROR: Must set PRIVATE_KEY in .env file or environment variable")
        return 1
    
    try:
        account: LocalAccount = Account.from_key(PRIVATE_KEY)
    except Exception as e:
        print(f"❌ ERROR: Failed to load account from private key: {e}")
        return 1
    
    print(f"\n📋 Configuration:")
    print(f"  Account: {account.address}")
    print(f"  API URL: {API_URL}")
    print(f"  Token Index: {TOKEN}")
    print(f"  Network: {'Mainnet' if USE_MAINNET else 'Testnet'}")
    print(f"  Mode: {'DRY RUN' if DRY_RUN else 'LIVE'}")
    
    # Determine which storage slot method to use
    finalize_action: FinalizeEvmContractAction
    if USE_CUSTOM_STORAGE_SLOT:
        finalize_action = {
            "type": "finalizeEvmContract",
            "token": TOKEN,
            "input": "customStorageSlot",
        }
        storage_slot_info = "Custom storage slot (keccak256('HyperCore deployer'))"
    elif USE_DEPLOY_NONCE:
        finalize_action = {
            "type": "finalizeEvmContract",
            "token": TOKEN,
            "input": {"create": {"nonce": DEPLOY_NONCE}},
        }
        storage_slot_info = f"Deploy nonce: {DEPLOY_NONCE}"
    elif USE_FIRST_STORAGE_SLOT:
        finalize_action = {
            "type": "finalizeEvmContract",
            "token": TOKEN,
            "input": "firstStorageSlot",
        }
        storage_slot_info = "First storage slot"
    else:
        raise Exception("Must set one of: USE_CUSTOM_STORAGE_SLOT, USE_DEPLOY_NONCE, or USE_FIRST_STORAGE_SLOT")
    
    # Sign the action
    print(f"\n🔐 Signing transaction...")
    try:
        nonce = get_timestamp_ms()
        signature = sign_l1_action(account, finalize_action, None, nonce, None, USE_MAINNET)
        payload = {
            "action": finalize_action,
            "nonce": nonce,
            "signature": signature,
            "vaultAddress": None,
        }
        print("✅ Transaction signed successfully")
    except Exception as e:
        print(f"❌ ERROR: Failed to sign transaction: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Display what will be sent
    print("\n" + "="*80)
    print("TRANSACTION DETAILS")
    print("="*80)
    print(f"API Endpoint: {API_URL}/exchange")
    print(f"Token Index: {TOKEN}")
    print(f"Storage Slot Method: {storage_slot_info}")
    print(f"Nonce: {nonce}")
    print("\nAction that will be sent:")
    print(json.dumps(finalize_action, indent=2))
    print("\nFull payload (signature truncated for display):")
    payload_display = payload.copy()
    if "signature" in payload_display:
        sig = payload_display["signature"]
        payload_display["signature"] = {
            "r": sig["r"][:20] + "..." if len(sig["r"]) > 20 else sig["r"],
            "s": sig["s"][:20] + "..." if len(sig["s"]) > 20 else sig["s"],
            "v": sig["v"]
        }
    print(json.dumps(payload_display, indent=2))
    print("="*80)
    print("⚠️  WARNING: This action is IRREVERSIBLE!")
    print("="*80)
    
    if DRY_RUN:
        print("\n🔍 DRY RUN MODE - Transaction NOT sent")
        print("Set DRY_RUN = False to actually send this transaction")
    else:
        print("\n📤 SENDING TRANSACTION...")
        try:
            response = requests.post(API_URL + "/exchange", json=payload, timeout=30)
            response.raise_for_status()  # Raises an HTTPError for bad responses
            
            result = response.json()
            print("\n✅ Transaction submitted successfully!")
            print("Response:")
            print(json.dumps(result, indent=2))
            
            # Check for errors in the response
            if isinstance(result, dict):
                if result.get("status") == "ok":
                    print("\n✅ Status: OK - Transaction accepted")
                    if "response" in result:
                        print(f"Response data: {json.dumps(result['response'], indent=2)}")
                elif result.get("status") == "err":
                    error_msg = result.get("response", "Unknown error")
                    print(f"\n❌ Status: ERROR - {error_msg}")
                    if isinstance(error_msg, dict) and "data" in error_msg:
                        print(f"Error details: {error_msg['data']}")
                    return 1
                else:
                    print(f"\n⚠️  Status: {result.get('status', 'unknown')}")
                    print("Full response:", json.dumps(result, indent=2))
            else:
                print(f"\n⚠️  Unexpected response format: {result}")
                
        except requests.exceptions.Timeout:
            print("\n❌ ERROR: Request timed out after 30 seconds")
            print("The transaction may have been submitted. Check your account status.")
            return 1
        except requests.exceptions.HTTPError as e:
            print(f"\n❌ HTTP ERROR: {e}")
            print(f"Status code: {response.status_code}")
            try:
                error_body = response.json()
                print(f"Error response: {json.dumps(error_body, indent=2)}")
            except:
                print(f"Error response (text): {response.text}")
            return 1
        except requests.exceptions.RequestException as e:
            print(f"\n❌ REQUEST ERROR: {e}")
            print("Failed to send transaction. Check your network connection and API endpoint.")
            return 1
        except Exception as e:
            print(f"\n❌ UNEXPECTED ERROR: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    return 0


if __name__ == "__main__":
    import sys
    exit_code = main()
    if exit_code != 0:
        print("\n" + "="*80)
        print("❌ Script completed with errors")
        print("="*80)
    else:
        print("\n" + "="*80)
        print("✅ Script completed successfully")
        print("="*80)
    sys.exit(exit_code)

