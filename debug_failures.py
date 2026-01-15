"""
Debug tool to test failed stores individually with full logging.
"""

import asyncio
from shopify_verifier import ShopifyVerifier

async def debug_store(store_url: str):
    """Run verification with full debugging enabled."""
    print(f"\n{'='*70}")
    print(f"DEBUGGING: {store_url}")
    print(f"{'='*70}\n")
    
    verifier = ShopifyVerifier(
        headless=False,  # Show browser
        debug=True,      # Full logging
        timeout=30000    # 30 second timeout
    )
    
    async with verifier:
        result = await verifier.verify_store(store_url)
    
    print(f"\n{'='*70}")
    print(f"RESULT SUMMARY")
    print(f"{'='*70}")
    print(f"Success: {result.success}")
    print(f"Reached checkout: {result.reached_checkout}")
    print(f"Error: {result.error_message}")
    print(f"Product found: {result.product_url}")
    
    if result.reached_checkout:
        print(f"\nCurrency:")
        print(f"  Multiple currencies: {result.multiple_currencies_supported}")
        print(f"  Available countries: {len(result.available_countries)}")
        print(f"  Currency switch tested: {result.currency_switch_tested}")
        
        print(f"\nPost-purchase:")
        print(f"  Detected: {result.post_purchase_upsell_detected}")
        print(f"  App: {result.post_purchase_app_name}")
    
    return result


async def main():
    """Test the failed stores."""
    
    # Failed stores from the batch run
    failed_stores = [
        "https://prosupps.com",
        "https://nocoldfeet.co",
        # Skip the SSL error one for now: "https://heyjuguets-de.shop"
    ]
    
    print("This will test each failed store with browser visible and full logging.")
    print("Watch what happens and we can identify the issue.\n")
    
    for store in failed_stores:
        try:
            await debug_store(store)
        except KeyboardInterrupt:
            print("\n\nStopped by user")
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
        
        print("\n\nPress Enter to continue to next store (or Ctrl+C to stop)...")
        input()


if __name__ == "__main__":
    asyncio.run(main())
