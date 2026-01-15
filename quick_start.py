"""
Quick Start Script for Shopify Verifier

Run this to test the verifier with a few example stores.
"""

import asyncio
from shopify_verifier import ShopifyVerifier


async def main():
    """Quick test with a few well-known Shopify stores."""
    
    # Sample stores to test
    test_stores = [
        "https://weareplufl.com",
        "https://www.allbirds.com",
        "https://www.bombas.com",
    ]
    
    print("\n" + "="*70)
    print("SHOPIFY STORE VERIFIER - QUICK START")
    print("="*70)
    print(f"\nTesting {len(test_stores)} stores...")
    print("This will take a few minutes. Watch the browser automation in action!")
    print("\nNOTE: Set headless=True in the code below to hide the browser window.\n")
    
    # Initialize verifier (headless=False shows the browser)
    verifier = ShopifyVerifier(headless=False, timeout=30000)
    
    results = []
    
    for i, store_url in enumerate(test_stores, 1):
        print(f"\n{'='*70}")
        print(f"[{i}/{len(test_stores)}] Testing: {store_url}")
        print("="*70)
        
        result = await verifier.verify_store(store_url)
        results.append(result)
        
        # Print quick summary
        if result.success:
            print(f"\n✓ SUCCESS")
            print(f"  Multi-currency support: {'Yes' if result.multiple_currencies_supported else 'No'}")
            if result.detected_currencies:
                print(f"  Currencies detected: {', '.join(result.detected_currencies)}")
            print(f"  Post-purchase upsell: {'Yes' if result.post_purchase_upsell_detected else 'No'}")
            if result.post_purchase_details:
                print(f"  Upsell details: {result.post_purchase_details}")
        else:
            print(f"\n✗ FAILED: {result.error_message}")
    
    # Final summary
    print(f"\n{'='*70}")
    print("FINAL SUMMARY")
    print("="*70)
    
    successful = sum(1 for r in results if r.success)
    with_currencies = sum(1 for r in results if r.multiple_currencies_supported)
    with_upsells = sum(1 for r in results if r.post_purchase_upsell_detected)
    
    print(f"Total tested: {len(results)}")
    print(f"Successful: {successful}/{len(results)}")
    print(f"With multi-currency: {with_currencies}/{len(results)}")
    print(f"With post-purchase upsells: {with_upsells}/{len(results)}")
    print("\n" + "="*70)
    print("\nNext steps:")
    print("1. For batch processing, see: batch_verifier.py")
    print("2. For detailed usage, see: README.md")
    print("3. To hide the browser, set headless=True in this script")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
