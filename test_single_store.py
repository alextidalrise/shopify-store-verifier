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
    
    print(f"\n--- Currency Detection ---")
    print(f"Currency selector found: {result.currency_selector_found}")
    print(f"Multiple currencies supported: {result.multiple_currencies_supported}")
    print(f"Detected currencies: {result.detected_currencies}")
    print(f"Homepage currency: {result.homepage_currency}")
    print(f"Checkout currency: {result.checkout_currency}")
    
    print(f"\n--- Post-Purchase Upsells ---")
    print(f"Detected: {result.post_purchase_upsell_detected}")
    if result.post_purchase_details:
        print(f"Details: {result.post_purchase_details}")
    
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
    
    test_store = "https://www.allbirds.com"
    
    # Set to True to hide browser, False to watch it work
    show_browser = True
    
    # Enable extra logging and screenshots for debugging
    debug_mode = True
    
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
