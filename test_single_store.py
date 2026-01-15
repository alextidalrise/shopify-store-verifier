"""
Single Store Test Script

Quick iteration tool for testing a single store.
Perfect for debugging and rapid development.
"""

import asyncio
from shopify_verifier import ShopifyVerifier


async def test_single_store(store_url: str, headless: bool = False, debug: bool = True):
    """
    Test a single store with detailed output.
    
    Args:
        store_url: The store URL to test
        headless: False = show browser (default), True = hide browser
        debug: True = extra logging and screenshots (default), False = normal mode
    """
    print("\n" + "="*70)
    print(f"SINGLE STORE TEST")
    print("="*70)
    print(f"Store: {store_url}")
    print(f"Headless: {headless}")
    print(f"Debug mode: {debug}")
    print("="*70 + "\n")
    
    verifier = ShopifyVerifier(headless=headless, timeout=30000, debug=debug)
    result = await verifier.verify_store(store_url)
    
    # Print detailed results
    print("\n" + "="*70)
    print("RESULTS")
    print("="*70)
    
    print(f"\n{'SUCCESS' if result.success else 'FAILED'}")
    
    if result.error_message:
        print(f"\nError: {result.error_message}")
    
    print(f"\n--- Currency Verification ---")
    print(f"Multiple currencies supported: {result.multiple_currencies_supported}")
    print(f"Available countries: {len(result.available_countries)} - {result.available_countries[:5]}{'...' if len(result.available_countries) > 5 else ''}")
    print(f"Country-currency pairs detected: {result.country_currency_pairs}")
    print(f"Currency switch tested: {result.currency_switch_tested}")
    print(f"Currency switch successful: {result.currency_switch_successful}")
    print(f"Initial currency: {result.initial_currency}")
    print(f"Switched currency: {result.switched_currency}")
    
    print(f"\n--- Post-Purchase Upsells ---")
    print(f"Detected: {result.post_purchase_upsell_detected}")
    if result.post_purchase_app_name:
        print(f"App: {result.post_purchase_app_name}")
    if result.post_purchase_requests:
        print(f"Requests detected: {len(result.post_purchase_requests)}")
        for req in result.post_purchase_requests[:2]:
            print(f"  - {req[:80]}...")
    
    print(f"\n--- Debug Info ---")
    print(f"Product URL: {result.product_url}")
    print(f"Reached checkout: {result.reached_checkout}")
    
    print("\n" + "="*70 + "\n")
    
    return result


async def main():
    """
    Edit the store URL below to test different stores quickly.
    """
    
    # ============================================
    # EDIT THIS LINE TO TEST DIFFERENT STORES
    # ============================================
    
    test_store = "https://geteuvella.com"  # Test cart verification
    
    # Set to True to hide browser, False to watch it work
    show_browser = False  # Headless for speed
    
    # Enable extra logging and screenshots for debugging
    debug_mode = True  # Shows detailed product availability checking
    
    # ============================================
    
    await test_single_store(test_store, headless=not show_browser, debug=debug_mode)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("QUICK TEST - SINGLE STORE VERIFIER")
    print("="*70)
    print("\nTo test a different store, edit the 'test_store' variable in this file.")
    print("Set show_browser=False to run in headless mode (faster).")
    print("\nStarting test...\n")
    
    asyncio.run(main())
