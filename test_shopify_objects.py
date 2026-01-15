"""
Test script to discover what Shopify objects are available on checkout page.
"""

import asyncio
from playwright.async_api import async_playwright

async def discover_shopify_objects(store_url: str):
    """Check what Shopify objects are available on checkout."""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        print(f"Testing: {store_url}")
        print("="*70)
        
        # Navigate to checkout (this will require having items in cart)
        # For now, let's just try the homepage first
        await page.goto(store_url)
        await page.wait_for_timeout(2000)
        
        # Check what Shopify objects exist
        shopify_data = await page.evaluate("""() => {
            const data = {};
            
            // Check if Shopify object exists
            if (typeof Shopify !== 'undefined') {
                data.shopify_exists = true;
                
                // Common properties
                if (Shopify.shop) data.shop = Shopify.shop;
                if (Shopify.currency) data.currency = Shopify.currency;
                if (Shopify.country) data.country = Shopify.country;
                if (Shopify.locale) data.locale = Shopify.locale;
                if (Shopify.theme) data.theme = Shopify.theme;
                
                // Try to get all keys
                data.shopify_keys = Object.keys(Shopify);
            } else {
                data.shopify_exists = false;
            }
            
            // Check window objects
            if (window.meta) data.window_meta = window.meta;
            if (window.theme) data.window_theme = window.theme;
            
            // Check for checkout-specific objects
            if (typeof ShopifyAnalytics !== 'undefined') {
                data.analytics = {
                    currency: ShopifyAnalytics.meta?.currency,
                    shop: ShopifyAnalytics.meta?.shop
                };
            }
            
            return data;
        }""")
        
        print("\nSHOPIFY OBJECTS FOUND:")
        print("-"*70)
        import json
        print(json.dumps(shopify_data, indent=2))
        
        await browser.close()

async def main():
    # Test on a known store
    stores_to_test = [
        "https://itsbronze.com",
        "https://prosupps.com",
    ]
    
    for store in stores_to_test:
        await discover_shopify_objects(store)
        print("\n\n")

if __name__ == "__main__":
    asyncio.run(main())
