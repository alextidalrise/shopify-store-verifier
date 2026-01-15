"""
Shopify Store Verifier
Checks if stores support:
1. Multiple currencies with local currency checkout
2. Post-purchase upsells

Uses Playwright for robust browser automation across different store themes.
"""

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout


@dataclass
class VerificationResult:
    """Results from verifying a Shopify store."""
    store_url: str
    success: bool
    error_message: Optional[str] = None
    
    # Currency verification (updated approach)
    multiple_currencies_supported: bool = False
    available_countries: list[str] = None
    country_currency_pairs: dict = None  # e.g., {"US": "USD", "GB": "GBP"}
    currency_switch_tested: bool = False
    currency_switch_successful: bool = False
    initial_currency: Optional[str] = None
    switched_currency: Optional[str] = None
    
    # Post-purchase verification (updated approach)
    post_purchase_upsell_detected: bool = False
    post_purchase_app_name: Optional[str] = None
    post_purchase_requests: list[str] = None
    
    # Debug info
    product_url: Optional[str] = None
    reached_checkout: bool = False
    
    def __post_init__(self):
        if self.available_countries is None:
            self.available_countries = []
        if self.country_currency_pairs is None:
            self.country_currency_pairs = {}
        if self.post_purchase_requests is None:
            self.post_purchase_requests = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "store_url": self.store_url,
            "success": self.success,
            "error_message": self.error_message,
            "multiple_currencies_supported": self.multiple_currencies_supported,
            "available_countries": self.available_countries,
            "country_currency_pairs": self.country_currency_pairs,
            "currency_switch_tested": self.currency_switch_tested,
            "currency_switch_successful": self.currency_switch_successful,
            "initial_currency": self.initial_currency,
            "switched_currency": self.switched_currency,
            "post_purchase_upsell_detected": self.post_purchase_upsell_detected,
            "post_purchase_app_name": self.post_purchase_app_name,
            "post_purchase_requests": self.post_purchase_requests,
            "product_url": self.product_url,
            "reached_checkout": self.reached_checkout,
        }


class ShopifyVerifier:
    """Verifies Shopify stores for currency support and post-purchase upsells."""
    
    # Pop-up close button patterns (various types of pop-ups)
    # Common "Add to Cart" button patterns
    ADD_TO_CART_PATTERNS = [
        'button[name="add"]',
        'button[type="submit"][name="add"]',
        '[id*="AddToCart"]',
        '[class*="add-to-cart"]',
        '[class*="addtocart"]',
        'button:has-text("Add to cart")',
        'button:has-text("Add to bag")',
        'input[type="submit"][value*="Add to cart" i]',
    ]
    
    # Checkout button patterns in cart
    CHECKOUT_BUTTON_PATTERNS = [
        'button[name="checkout"]',
        'a[href*="/checkout"]',
        'button:has-text("Checkout")',
        'button:has-text("Check out")',
        '[class*="checkout-button"]',
        'input[type="submit"][name="checkout"]',
    ]
    
    # Country to currency mapping for intelligent testing
    # This helps us identify which countries use different currencies
    COUNTRY_CURRENCY_MAP = {
        # North America
        'US': 'USD', 'USA': 'USD', 'United States': 'USD',
        'CA': 'CAD', 'Canada': 'CAD',
        'MX': 'MXN', 'Mexico': 'MXN',
        
        # Europe - Euro countries
        'AT': 'EUR', 'Austria': 'EUR',
        'BE': 'EUR', 'Belgium': 'EUR',
        'DE': 'EUR', 'Germany': 'EUR',
        'ES': 'EUR', 'Spain': 'EUR',
        'FR': 'EUR', 'France': 'EUR',
        'IE': 'EUR', 'Ireland': 'EUR',
        'IT': 'EUR', 'Italy': 'EUR',
        'NL': 'EUR', 'Netherlands': 'EUR',
        'PT': 'EUR', 'Portugal': 'EUR',
        'FI': 'EUR', 'Finland': 'EUR',
        'GR': 'EUR', 'Greece': 'EUR',
        
        # Europe - Non-Euro
        'GB': 'GBP', 'UK': 'GBP', 'United Kingdom': 'GBP',
        'CH': 'CHF', 'Switzerland': 'CHF',
        'NO': 'NOK', 'Norway': 'NOK',
        'SE': 'SEK', 'Sweden': 'SEK',
        'DK': 'DKK', 'Denmark': 'DKK',
        'PL': 'PLN', 'Poland': 'PLN',
        'CZ': 'CZK', 'Czech Republic': 'CZK',
        
        # Asia Pacific
        'AU': 'AUD', 'Australia': 'AUD',
        'NZ': 'NZD', 'New Zealand': 'NZD',
        'JP': 'JPY', 'Japan': 'JPY',
        'CN': 'CNY', 'China': 'CNY',
        'HK': 'HKD', 'Hong Kong': 'HKD',
        'SG': 'SGD', 'Singapore': 'SGD',
        'KR': 'KRW', 'South Korea': 'KRW',
        'IN': 'INR', 'India': 'INR',
        'TH': 'THB', 'Thailand': 'THB',
        'MY': 'MYR', 'Malaysia': 'MYR',
        'ID': 'IDR', 'Indonesia': 'IDR',
        'PH': 'PHP', 'Philippines': 'PHP',
        'VN': 'VND', 'Vietnam': 'VND',
        
        # Middle East & Africa
        'AE': 'AED', 'United Arab Emirates': 'AED',
        'SA': 'SAR', 'Saudi Arabia': 'SAR',
        'IL': 'ILS', 'Israel': 'ILS',
        'ZA': 'ZAR', 'South Africa': 'ZAR',
        
        # South America
        'BR': 'BRL', 'Brazil': 'BRL',
        'AR': 'ARS', 'Argentina': 'ARS',
        'CL': 'CLP', 'Chile': 'CLP',
        'CO': 'COP', 'Colombia': 'COP',
    }
    
    def __init__(self, headless: bool = True, timeout: int = 30000, debug: bool = False):
        """
        Initialize the verifier.
        
        Args:
            headless: Run browser in headless mode
            timeout: Default timeout in milliseconds
            debug: Enable debug mode with extra logging and screenshots
        """
        self.headless = headless
        self.timeout = timeout
        self.debug = debug
        
    def _normalize_url(self, url: str) -> str:
        """Normalize store URL."""
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    async def _add_product_to_cart_via_api(self, page: Page, variant_id: str, base_url: str) -> bool:
        """
        Add product to cart using Shopify's Cart API.
        
        Args:
            page: Playwright page object
            variant_id: The variant ID to add to cart
            base_url: Store base URL
        
        Returns:
            True if successfully added to cart
        """
        try:
            print(f"  Adding variant {variant_id} to cart via API...")
            print(f"  [DEBUG] Base URL: {base_url}")
            print(f"  [DEBUG] Current page URL: {page.url}")
            
            # Try multiple Cart API formats
            import json
            
            # Execute fetch in browser context (has cookies/session)
            try:
                if self.debug:
                    print(f"  [DEBUG] Preparing Cart API request...")
                    print(f"  [DEBUG] Variant ID (type: {type(variant_id)}): {variant_id}")
                
                # Execute fetch directly in the page context (like browser console)
                result = await page.evaluate("""
                    async (variantId) => {
                        console.log('[Cart API] Starting request with variant:', variantId);
                        
                        const requestBody = {
                            items: [{
                                id: variantId,
                                quantity: 1
                            }]
                        };
                        
                        console.log('[Cart API] Request body:', JSON.stringify(requestBody));
                        
                        try {
                            const response = await fetch('/cart/add.js', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify(requestBody)
                            });
                            
                            console.log('[Cart API] Response status:', response.status);
                            console.log('[Cart API] Response ok:', response.ok);
                            
                            const data = await response.json();
                            console.log('[Cart API] Response data:', JSON.stringify(data));
                            
                            if (response.ok) {
                                return { 
                                    success: true, 
                                    status: response.status,
                                    data: data,
                                    requestBody: requestBody 
                                };
                            } else {
                                return { 
                                    success: false, 
                                    status: response.status, 
                                    error: data,
                                    requestBody: requestBody
                                };
                            }
                        } catch (error) {
                            console.error('[Cart API] Exception:', error);
                            return { 
                                success: false, 
                                error: error.message,
                                errorName: error.name,
                                requestBody: requestBody
                            };
                        }
                    }
                """, int(variant_id))
                
                if result.get('success'):
                    print(f"  [DEBUG] Cart API returned success")
                    print(f"  [DEBUG] Full API response: {json.dumps(result, indent=2)}")
                    
                    response_data = result.get('data', {})
                    
                    # Note: /cart/add.js doesn't return item_count, only items array
                    items_array = response_data.get('items', []) if isinstance(response_data, dict) else []
                    item_count = len(items_array)
                    
                    if item_count > 0:
                        print(f"  ✓ Cart API success - added {item_count} item(s) to cart")
                        if self.debug and isinstance(response_data, dict):
                            print(f"  [DEBUG] Response keys: {list(response_data.keys())}")
                            print(f"  [DEBUG] Items in response: {len(items_array)}")
                            if items_array:
                                first_item = items_array[0]
                                print(f"  [DEBUG] First item: variant_id={first_item.get('variant_id')}, quantity={first_item.get('quantity')}")
                        
                        print(f"Product added to cart")
                        return True
                    else:
                        print(f"  ✗ Cart API returned success but no items in response")
                        print(f"  [DEBUG] Response data: {json.dumps(response_data, indent=2) if isinstance(response_data, dict) else response_data}")
                        return False
                else:
                    print(f"  [DEBUG] Cart API returned failure")
                    print(f"  [DEBUG] Full error response: {json.dumps(result, indent=2)}")
                    
                    error_msg = result.get('error', result.get('status', 'Unknown error'))
                    status = result.get('status', 'N/A')
                    print(f"  ✗ Cart API failed: {error_msg} (Status: {status})")
                    
                    if 'requestBody' in result:
                        print(f"  [DEBUG] Request that failed: {json.dumps(result['requestBody'])}")
                    
                    return False
                    
            except Exception as e:
                print(f"  [DEBUG] Exception in Cart API call: {type(e).__name__}")
                print(f"  ✗ Cart API error: {str(e)[:80]}")
                import traceback
                if self.debug:
                    print(f"  [DEBUG] Traceback:\n{traceback.format_exc()}")
                return False
                
        except Exception as e:
            print(f"  [DEBUG] Outer exception: {type(e).__name__}")
            print(f"  ✗ Error using Cart API: {str(e)[:80]}")
            import traceback
            if self.debug:
                print(f"  [DEBUG] Traceback:\n{traceback.format_exc()}")
            return False
    
    async def _navigate_to_checkout(self, page: Page) -> tuple[bool, Optional[str]]:
        """
        Navigate to checkout page.
        
        Returns:
            Tuple of (success, error_message)
        """
        # Since we use Cart API, we should directly navigate to checkout
        try:
            # Get the base URL from current page
            current_url = page.url
            if '/products.json' in current_url:
                base_url = current_url.split('/products.json')[0]
            else:
                base_url = self._normalize_url(current_url)
            
            print(f"Navigating to checkout: {base_url}/checkout")
            
            # Direct navigation to checkout
            response = await page.goto(f"{base_url}/checkout", wait_until="domcontentloaded", timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Check if we reached checkout
            final_url = page.url
            if '/checkout' in final_url or 'checkout.shopify.com' in final_url:
                print(f"  ✓ Reached checkout")
                return True, None
            
            # Check for common redirect issues
            if 'cart' in final_url:
                return False, "Redirected to cart (cart may be empty or checkout disabled)"
            elif 'password' in final_url:
                return False, "Store is password protected"
            elif response and response.status == 404:
                return False, "Checkout page returned 404"
            elif final_url == base_url or final_url == f"{base_url}/" or final_url.rstrip('/') == base_url.rstrip('/'):
                return False, "Redirected to homepage (cart empty or checkout not available)"
            else:
                return False, f"Unexpected redirect to: {final_url}"
                
        except Exception as e:
            error_msg = str(e)
            if 'timeout' in error_msg.lower():
                return False, "Timeout navigating to checkout"
            elif 'net::' in error_msg:
                return False, f"Network error: {error_msg[:100]}"
            else:
                return False, f"Checkout navigation error: {error_msg[:100]}"
    
    async def _get_checkout_currency(self, page: Page) -> Optional[str]:
        """
        Extract currency from checkout page by finding <abbr> elements with 3-letter codes.
        
        Returns:
            Currency code (e.g., 'USD', 'GBP') or None
        """
        try:
            # Look for <abbr> elements which typically contain currency codes
            abbr_elements = await page.locator('abbr').all()
            
            for abbr in abbr_elements:
                text = await abbr.text_content()
                if text and len(text.strip()) == 3 and text.strip().isupper():
                    currency = text.strip()
                    # Validate it looks like a currency code
                    if re.match(r'^[A-Z]{3}$', currency):
                        return currency
            
            return None
        except Exception as e:
            if self.debug:
                print(f"  Error detecting checkout currency: {str(e)[:50]}")
            return None
    
    async def _get_available_countries(self, page: Page) -> tuple[list[str], Optional[str]]:
        """
        Get list of available countries from the country selector in checkout.
        
        Returns:
            Tuple of (list of country codes/names, currently selected country)
        """
        try:
            # Look for the country selector
            country_select = page.locator('select[name="countryCode"]').first
            
            if await country_select.count() == 0:
                if self.debug:
                    print("  No country selector found")
                return [], None
            
            # Get currently selected option
            selected_value = await country_select.evaluate('el => el.value')
            
            # Get all available options
            options = await country_select.locator('option').all()
            countries = []
            
            for option in options:
                value = await option.get_attribute('value')
                text = await option.text_content()
                if value:
                    countries.append(value)
                    if self.debug:
                        print(f"    Found country: {text} ({value})")
            
            return countries, selected_value
            
        except Exception as e:
            if self.debug:
                print(f"  Error getting countries: {str(e)[:80]}")
            return [], None
    
    def _get_expected_currency(self, country_code: str) -> Optional[str]:
        """
        Get expected currency for a country code.
        
        Args:
            country_code: 2-letter country code (e.g., 'US', 'GB')
            
        Returns:
            Expected currency code or None
        """
        # Try exact match first
        if country_code in self.COUNTRY_CURRENCY_MAP:
            return self.COUNTRY_CURRENCY_MAP[country_code]
        
        # Try case-insensitive match
        for key, value in self.COUNTRY_CURRENCY_MAP.items():
            if key.upper() == country_code.upper():
                return value
        
        return None
    
    async def _test_currency_switch(self, page: Page, store_base_currency: str = None) -> dict:
        """
        Test if switching countries in checkout changes the currency.
        
        Returns:
            Dict with test results including currencies detected and whether switch worked
        """
        result = {
            'tested': False,
            'initial_country': None,
            'initial_currency': None,
            'switched_country': None,
            'switched_currency': None,
            'currency_changed': False,
            'available_countries': [],
            'country_currency_pairs': {},
        }
        
        try:
            print("  Testing currency switching in checkout...")
            
            # Get available countries
            countries, initial_country = await self._get_available_countries(page)
            result['available_countries'] = countries
            result['initial_country'] = initial_country
            
            if not countries:
                print("  No country selector found - single market store")
                return result
            
            if len(countries) == 1:
                print(f"  Only 1 country available ({countries[0]}) - single market store")
                return result
            
            print(f"  Found {len(countries)} countries in selector")
            
            # Get initial currency
            initial_currency = await self._get_checkout_currency(page)
            result['initial_currency'] = initial_currency
            
            if not initial_currency:
                print("  Could not detect initial currency")
                return result
            
            print(f"  Initial: {initial_country} → {initial_currency}")
            result['country_currency_pairs'][initial_country] = initial_currency
            
            # Find countries to test - prioritize store's base currency for post-purchase detection
            countries_to_test = []
            
            # First, try to find a country matching the store's base currency
            if store_base_currency and store_base_currency != initial_currency:
                print(f"  Store base currency is {store_base_currency}, looking for matching country...")
                for country in countries:
                    if country != initial_country:
                        expected_currency = self._get_expected_currency(country)
                        if expected_currency == store_base_currency:
                            countries_to_test.append(country)
                            print(f"  Will test {country} (matches store base currency: {store_base_currency})")
                            break
            
            # If no base currency match or no base currency info, try US (most common)
            if not countries_to_test and 'US' in countries and initial_country != 'US':
                countries_to_test.append('US')
            
            # Then find a country with different currency for proper currency testing
            initial_expected_currency = self._get_expected_currency(initial_country)
            for country in countries:
                if country not in countries_to_test and country != initial_country:
                    expected_currency = self._get_expected_currency(country)
                    if expected_currency and expected_currency != initial_expected_currency:
                        countries_to_test.append(country)
                        break  # Just need one different currency
            
            if not countries_to_test:
                print("  All countries use same currency - no switch test needed")
                return result
            
            country_select = page.locator('select[name="countryCode"]').first
            
            # Test each country (this triggers post-purchase as we change selector)
            for i, test_country in enumerate(countries_to_test):
                expected_currency = self._get_expected_currency(test_country)
                print(f"  Testing country {i+1}/{len(countries_to_test)}: {test_country} (expect {expected_currency})")
                
                await country_select.select_option(test_country)
                result['tested'] = True
                
                # Wait for currency to update and post-purchase to potentially fire
                await page.wait_for_timeout(3000)
                
                # Check currency
                new_currency = await self._get_checkout_currency(page)
                if new_currency:
                    result['country_currency_pairs'][test_country] = new_currency
                    print(f"    → {new_currency}")
                    
                    if new_currency != initial_currency:
                        result['currency_changed'] = True
                        result['switched_country'] = test_country
                        result['switched_currency'] = new_currency
            
            # Report results
            unique_currencies = set(result['country_currency_pairs'].values())
            if len(unique_currencies) > 1:
                print(f"  ✅ Detected multiple currencies: {unique_currencies}")
            else:
                print(f"  ℹ️  All tested countries use {initial_currency}")
            
            return result
            
        except Exception as e:
            print(f"  Error testing currency switch: {str(e)[:100]}")
            return result
    
    async def verify_store(self, store_url: str) -> VerificationResult:
        """
        Verify a single Shopify store.
        
        Args:
            store_url: The store URL to verify
            
        Returns:
            VerificationResult with all findings
        """
        base_url = self._normalize_url(store_url)
        result = VerificationResult(store_url=base_url, success=False)
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            
            try:
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )
                page = await context.new_page()
                
                # Capture browser console messages for debugging
                if self.debug:
                    def log_console_message(msg):
                        # Only log Cart API related messages to reduce noise
                        text = msg.text
                        if '[Cart' in text or 'cart' in text.lower():
                            msg_type = msg.type
                            print(f"  [BROWSER CONSOLE - {msg_type.upper()}] {text}")
                    
                    page.on("console", log_console_message)
                
                # Step 0: Fetch store metadata to get base currency
                print(f"Fetching store metadata...")
                store_base_currency = None
                store_base_country = None
                try:
                    meta_response = await page.request.get(f"{base_url}/meta.json")
                    if meta_response.ok:
                        meta_data = await meta_response.json()
                        store_base_currency = meta_data.get('currency')
                        store_base_country = meta_data.get('country')
                        if store_base_currency:
                            print(f"  Store base currency: {store_base_currency} (country: {store_base_country})")
                except:
                    pass  # Not critical, we can work without it
                
                # Step 1: Navigate directly to products.json to get product data AND establish session
                print(f"Loading {base_url}/products.json...")
                try:
                    await page.goto(f"{base_url}/products.json?limit=50", wait_until="domcontentloaded", timeout=self.timeout)
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    error_str = str(e)
                    # More specific error detection
                    if 'ERR_NAME_NOT_RESOLVED' in error_str or 'DNS' in error_str:
                        result.error_message = "DNS resolution error (domain not configured properly)"
                    elif 'ERR_CERT_COMMON_NAME_INVALID' in error_str:
                        result.error_message = "SSL certificate error (certificate name mismatch)"
                    elif 'ERR_CERT' in error_str or 'SSL' in error_str:
                        result.error_message = "SSL certificate error (invalid/expired certificate)"
                    elif 'ERR_CONNECTION_REFUSED' in error_str:
                        result.error_message = "Connection refused (server not accepting connections)"
                    elif 'ERR_CONNECTION' in error_str:
                        result.error_message = "Connection failed (server unreachable)"
                    elif 'timeout' in error_str.lower():
                        result.error_message = "Timeout loading store (too slow or blocked)"
                    elif '404' in error_str:
                        result.error_message = "Store returned 404 (page not found)"
                    else:
                        result.error_message = f"Failed to load store: {error_str[:100]}"
                    print(f"  ✗ {result.error_message}")
                    return result
                
                # Step 2: Parse products.json from the page to find available variant
                print("Finding an available product...")
                try:
                    products_data = await page.evaluate("""() => {
                        try {
                            // The page should contain the JSON data
                            const preTag = document.querySelector('pre');
                            if (preTag) {
                                return JSON.parse(preTag.textContent);
                            }
                            // Fallback: try to get from body
                            return JSON.parse(document.body.textContent);
                        } catch (e) {
                            return null;
                        }
                    }""")
                    
                    if not products_data or 'products' not in products_data:
                        print("  ✗ Could not parse products.json")
                        result.error_message = "Could not parse products.json"
                        return result
                    
                    products = products_data.get('products', [])
                    print(f"  Found {len(products)} products, searching for available variant...")
                    
                    # Find first available variant
                    variant_id = None
                    product_handle = None
                    
                    for product in products:
                        product_handle = product.get('handle')
                        product_title = product.get('title', 'Unknown')
                        variants = product.get('variants', [])
                        
                        if self.debug:
                            print(f"    Checking: {product_title} ({len(variants)} variants)")
                        
                        for variant in variants:
                            vid = variant.get('id')
                            available = variant.get('available', False)
                            
                            if self.debug:
                                variant_title = variant.get('title', 'Default')
                                print(f"      - {variant_title}: available={available}")
                            
                            if available and vid:
                                variant_id = str(vid)
                                variant_title = variant.get('title', '')
                                print(f"  ✓ Found available variant:")
                                print(f"    Product: {product_title}")
                                print(f"    Variant: {variant_title}")
                                print(f"    ID: {variant_id}")
                                print(f"    Handle: {product_handle}")
                                break
                        
                        if variant_id:
                            break
                    
                    if not variant_id:
                        print("  ✗ No available variants found")
                        result.error_message = "No available variants found"
                        return result
                        
                except Exception as e:
                    print(f"  ✗ Error parsing products.json: {str(e)[:80]}")
                    result.error_message = f"Error parsing products.json: {str(e)[:80]}"
                    return result
                
                # Store product URL for reference
                result.product_url = f"{base_url}/products/{product_handle}" if product_handle else base_url
                
                # Step 3: Add to cart via API only
                print("Adding product to cart...")
                added = await self._add_product_to_cart_via_api(page, variant_id, base_url)
                
                if not added:
                    result.error_message = "Could not add product to cart via API"
                    return result
                
                print("Product added to cart")
                
                # Step 5: Set up network monitoring BEFORE navigating to checkout
                print("Setting up post-purchase monitoring...")
                detected_requests = []
                
                def handle_request(request):
                    url = request.url
                    
                    # Skip post-purchase SURVEYS (TripleWhale, etc.) - we only want UPSELLS
                    if 'survey' in url.lower() or 'feedback' in url.lower():
                        if self.debug:
                            print(f"  ⊘ Skipping survey request: {url[:80]}...")
                        return
                    
                    # Check for post-purchase UPSELL patterns
                    if 'post-purchase' in url.lower() or 'post_purchase' in url.lower() or 'ppShouldTrigger' in url:
                        if url not in detected_requests:  # Avoid duplicates
                            detected_requests.append(url)
                            print(f"  📡 Post-purchase detected: {url[:80]}...")
                
                # Attach listeners to both requests and responses
                page.on('request', handle_request)
                page.on('response', lambda response: handle_request(response.request))
                
                # Navigate to checkout
                print("Navigating to checkout...")
                checkout_reached, checkout_error = await self._navigate_to_checkout(page)
                
                if not checkout_reached:
                    result.error_message = f"Could not reach checkout: {checkout_error}"
                    return result
                
                result.reached_checkout = True
                print("Reached checkout page")
                await page.wait_for_timeout(3000)  # Initial page load
                
                # Step 6: Test currency switching in checkout
                # NOTE: Country selector changes often trigger post-purchase network requests!
                print("Testing currency verification...")
                currency_test = await self._test_currency_switch(page, store_base_currency=store_base_currency)
                
                result.available_countries = currency_test['available_countries']
                result.country_currency_pairs = currency_test['country_currency_pairs']
                result.currency_switch_tested = currency_test['tested']
                result.currency_switch_successful = currency_test['currency_changed']
                result.initial_currency = currency_test['initial_currency']
                result.switched_currency = currency_test['switched_currency']
                
                # Determine if multi-currency is supported
                unique_currencies = set(currency_test['country_currency_pairs'].values())
                if len(unique_currencies) > 1 and currency_test['currency_changed']:
                    result.multiple_currencies_supported = True
                    print(f"  ✅ Multi-currency verified: {unique_currencies}")
                elif len(currency_test['available_countries']) > 1:
                    print(f"  ℹ️  Multiple countries available but single currency")
                else:
                    print(f"  ℹ️  Single market store")
                
                # IMPORTANT: Wait longer for post-purchase requests triggered by country selector change
                # Some stores don't fire post-purchase until country is changed!
                print("Waiting for post-purchase network activity...")
                await page.wait_for_timeout(5000)  # Extended wait to catch delayed post-purchase triggers
                
                # Step 7: Analyze post-purchase network requests
                print("Analyzing post-purchase upsells...")
                result.post_purchase_requests = detected_requests
                result.post_purchase_upsell_detected = len(detected_requests) > 0
                
                # Extract app name from detected requests
                detected_app = None
                if detected_requests:
                    # Filter out survey-related apps
                    upsell_requests = [url for url in detected_requests 
                                     if 'survey' not in url.lower() and 'feedback' not in url.lower()]
                    
                    for url in upsell_requests:
                        # Skip TripleWhale survey URLs specifically
                        if 'triplewhale' in url.lower() and 'survey' in url.lower():
                            continue
                        
                        # Try multiple patterns to extract app name
                        patterns = [
                            r'/([a-z]+(?:-[a-z]+)?)-\d+/',  # aftersell-549
                            r'//start\.([a-z]+)\.(?:app|io|com)/',  # start.aftersell.app
                            r'//([a-z]+)\.(?:app|io|com)/',  # aftersell.app
                            r'/post-purchase/[^/]+/([a-z]+)',  # /post-purchase/handle/aftersell
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, url.lower())
                            if match:
                                app_raw = match.group(1)
                                
                                # Skip non-upsell apps
                                skip_apps = ['triplewhale', 'klaviyo', 'yotpo']
                                if app_raw in skip_apps:
                                    continue
                                
                                app_name_map = {
                                    'aftersell': 'AfterSell',
                                    'reconvert': 'ReConvert',
                                    'zipify': 'Zipify',
                                    'carthook': 'CartHook',
                                    'honeycomb': 'Honeycomb',
                                    'upsell': 'Upsell',
                                }
                                detected_app = app_name_map.get(app_raw, app_raw.title())
                                break
                        
                        if detected_app:
                            break
                
                result.post_purchase_app_name = detected_app
                
                if result.post_purchase_upsell_detected:
                    if detected_app:
                        print(f"  ✅ Post-purchase detected: {detected_app}")
                    else:
                        print(f"  ✅ Post-purchase detected (app unknown)")
                    if self.debug:
                        print(f"  Detected {len(detected_requests)} request(s):")
                        for req in detected_requests[:3]:  # Show first 3
                            print(f"    - {req[:100]}")
                else:
                    print(f"  No post-purchase upsells detected")
                
                # Mark as successful
                result.success = True
                print(f"Verification complete for {base_url}")
                
            except PlaywrightTimeout as e:
                result.error_message = f"Timeout: {str(e)}"
            except Exception as e:
                result.error_message = f"Error: {str(e)}"
            finally:
                await browser.close()
        
        return result
    
    async def verify_stores_batch(self, store_urls: list[str], max_concurrent: int = 3) -> list[VerificationResult]:
        """
        Verify multiple stores concurrently.
        
        Args:
            store_urls: List of store URLs to verify
            max_concurrent: Maximum number of concurrent verifications
            
        Returns:
            List of VerificationResults
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def verify_with_semaphore(url: str) -> VerificationResult:
            async with semaphore:
                return await self.verify_store(url)
        
        tasks = [verify_with_semaphore(url) for url in store_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle any exceptions
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(VerificationResult(
                    store_url=store_urls[i],
                    success=False,
                    error_message=f"Exception: {str(result)}"
                ))
            else:
                final_results.append(result)
        
        return final_results


async def main():
    """Example usage."""
    verifier = ShopifyVerifier(headless=False)  # Set to True for production
    
    # Test with a single store
    test_store = "https://weareplufl.com"
    
    print(f"\n{'='*60}")
    print(f"Testing: {test_store}")
    print(f"{'='*60}\n")
    
    result = await verifier.verify_store(test_store)
    
    # Print results
    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"Success: {result.success}")
    if result.error_message:
        print(f"Error: {result.error_message}")
    print(f"\nCurrency Support:")
    print(f"  - Multiple currencies supported: {result.multiple_currencies_supported}")
    print(f"  - Available countries: {result.available_countries}")
    print(f"  - Country-currency pairs: {result.country_currency_pairs}")
    print(f"  - Currency switch tested: {result.currency_switch_tested}")
    print(f"  - Currency switch successful: {result.currency_switch_successful}")
    print(f"  - Initial currency: {result.initial_currency}")
    print(f"  - Switched currency: {result.switched_currency}")
    print(f"\nPost-Purchase Upsells:")
    print(f"  - Detected: {result.post_purchase_upsell_detected}")
    print(f"  - App name: {result.post_purchase_app_name}")
    print(f"  - Requests detected: {len(result.post_purchase_requests) if result.post_purchase_requests else 0}")
    print(f"\nDebug Info:")
    print(f"  - Product URL: {result.product_url}")
    print(f"  - Reached checkout: {result.reached_checkout}")
    
    # Save to JSON
    with open('verification_result.json', 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"\nResults saved to verification_result.json")


if __name__ == "__main__":
    asyncio.run(main())
