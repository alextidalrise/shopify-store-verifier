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
    
    async def _select_variant(self, page: Page) -> bool:
        """
        Select a product variant (size, color, etc.) if required.
        Handles both dropdown selectors and button/swatch selectors.
        Uses a generic approach that works for any variant type.
        
        Returns:
            True if a variant was selected (or not needed), False if failed
        """
        variant_selected = False
        
        # Scroll down a bit to ensure variant selectors are in view
        try:
            await page.evaluate("window.scrollBy(0, 300)")
            await page.wait_for_timeout(500)
        except:
            pass
        
        # Strategy 1: Dropdown selectors (traditional)
        try:
            variant_selectors = await page.locator('select[name*="option"], select[id*="variant"]').count()
            if variant_selectors > 0:
                print(f"  Found {variant_selectors} dropdown variant selector(s)")
                selects = page.locator('select[name*="option"], select[id*="variant"]')
                count = await selects.count()
                for i in range(count):
                    try:
                        await selects.nth(i).select_option(index=1, timeout=2000)
                        print(f"    Selected option from dropdown {i+1}")
                        variant_selected = True
                    except:
                        pass
                await page.wait_for_timeout(500)
                return True
        except:
            pass
        
        # Strategy 1.5: Look for and handle variant group tabs (like MEN'S/WOMEN'S SIZES)
        # These are often containers that need to be activated before selecting the actual variant
        tab_container_patterns = [
            'fieldset legend',  # Common pattern: <fieldset><legend>Size</legend><buttons...>
            '[role="radiogroup"]',
            'div[class*="variant"] > div[class*="tab"]',
            'div[class*="option"] > button[role="tab"]',
        ]
        
        # Check if there are tab-like containers and ensure one is active
        for container_pattern in tab_container_patterns:
            try:
                containers = page.locator(container_pattern)
                count = await containers.count()
                if count > 0:
                    # Click the first tab/group to ensure it's active
                    first_tab = containers.first
                    if await first_tab.is_visible(timeout=1000):
                        try:
                            await first_tab.click(timeout=2000)
                            await page.wait_for_timeout(500)
                            print(f"    Clicked variant group/tab to activate options")
                        except:
                            pass  # May already be active
                    break
            except:
                continue
        
        # Strategy 2: Generic container-based variant selection
        # Find variant containers, then select first available option within them
        # This works for ANY variant type (size, color, material, etc.)
        
        container_patterns = [
            # Fieldset is the most semantic container for form options
            'fieldset',
            # Radio groups
            '[role="radiogroup"]',
            # Product option containers with data attributes (most specific)
            'div[data-product-option]',
            # Shopify-specific variant containers
            'div[class*="ProductOption"]',
            'div[class*="product-form__input"]',
            # Generic variant containers (less specific, checked last)
            'div[class*="variant-selector"]',
            'div[class*="product-variant"]',
        ]
        
        for container_pattern in container_patterns:
            try:
                containers = page.locator(container_pattern)
                container_count = await containers.count()
                
                if container_count == 0:
                    continue
                
                # Don't process if we found way too many (likely false matches)
                if container_count > 20:
                    print(f"  Skipping {container_pattern}: found {container_count} (too many, likely false matches)")
                    continue
                
                print(f"  Found {container_count} potential variant container(s): {container_pattern}")
                
                # Process each container (e.g., one for Size, one for Color)
                for container_idx in range(min(container_count, 10)):  # Max 10 variant types
                    try:
                        container = containers.nth(container_idx)
                        
                        # Skip if not visible
                        if not await container.is_visible(timeout=1000):
                            continue
                        
                        # Get container label/name for logging
                        container_name = "unknown"
                        try:
                            # Try to find a label or legend
                            label_elem = await container.locator('legend, label, [class*="label"]').first.text_content()
                            if label_elem:
                                container_name = label_elem.strip()[:30]
                        except:
                            pass
                        
                        print(f"    Variant group: {container_name}")
                        
                        # Within this container, find clickable variant options
                        # Look for various types of selectable elements
                        option_selectors = [
                            'input[type="radio"]',  # Radio buttons
                            'button:not([disabled])',  # Enabled buttons
                            'label[for]',  # Labels (often wrap hidden radios)
                            '[role="radio"]',  # ARIA radio role
                            'a[class*="swatch"]',  # Swatch links
                        ]
                        
                        for option_selector in option_selectors:
                            options = container.locator(option_selector)
                            option_count = await options.count()
                            
                            if option_count == 0:
                                continue
                            
                            print(f"      Found {option_count} options ({option_selector})")
                            
                            # Try to select first available option
                            for opt_idx in range(min(option_count, 15)):  # Try up to 15 options
                                try:
                                    option = options.nth(opt_idx)
                                    
                                    # Check if visible
                                    if not await option.is_visible(timeout=500):
                                        continue
                                    
                                    # Check if disabled/sold-out
                                    classes = await option.get_attribute('class') or ''
                                    aria_disabled = await option.get_attribute('aria-disabled') or ''
                                    disabled_attr = await option.get_attribute('disabled')
                                    aria_checked = await option.get_attribute('aria-checked') or ''
                                    
                                    # Skip if disabled or sold out
                                    if (disabled_attr is not None or
                                        aria_disabled == 'true' or
                                        'sold-out' in classes.lower() or
                                        'unavailable' in classes.lower() or
                                        'disabled' in classes.lower()):
                                        continue
                                    
                                    # Skip if already selected/checked
                                    if aria_checked == 'true':
                                        print(f"      Option {opt_idx + 1} already selected")
                                        variant_selected = True
                                        break
                                    
                                    # Try to get option value/text for logging
                                    option_text = "option"
                                    try:
                                        option_text = (await option.get_attribute('value') or 
                                                     await option.get_attribute('aria-label') or
                                                     await option.text_content() or
                                                     f"#{opt_idx + 1}")
                                        option_text = option_text.strip()[:20]
                                    except:
                                        pass
                                    
                                    # Skip buttons that are clearly not variant selectors
                                    # These are informational buttons, not selection buttons
                                    if option_selector == 'button:not([disabled])':
                                        non_variant_keywords = [
                                            'size chart', 'size guide', 'fit guide', 'sizing',
                                            'chart', 'guide', 'info', 'learn more', 'help',
                                            'measure', 'find your size'
                                        ]
                                        text_lower = option_text.lower()
                                        if any(keyword in text_lower for keyword in non_variant_keywords):
                                            print(f"      Skipping non-variant button: {option_text}")
                                            continue
                                    
                                    print(f"      Selecting: {option_text}")
                                    
                                    # Click the option
                                    await option.click(timeout=2000, force=False)
                                    await page.wait_for_timeout(800)  # Wait for JS updates
                                    
                                    variant_selected = True
                                    print(f"      ✓ Variant selected")
                                    break  # Move to next container
                                    
                                except Exception as e:
                                    continue
                            
                            # If we selected something in this container, move to next container
                            if variant_selected:
                                break
                        
                    except Exception as e:
                        continue
                
                # If we found and processed containers, stop looking
                if variant_selected or container_count > 0:
                    break
                    
            except:
                continue
        
        # Strategy 3: Direct button/radio search (no container)
        # If container approach didn't work, try to find variant buttons directly
        if not variant_selected:
            print(f"  Container approach didn't find variants, trying direct search...")
            
            direct_patterns = [
                # Allbirds-style: buttons inside list items (from browser inspection)
                'list button',
                'ul button',
                '[role="list"] button',
                # Buttons with aria-label containing "size" or "select"
                'button[aria-label*="size" i]',
                'button[aria-label*="Select" i]',
                # Allbirds-style: buttons with "Select size" text
                'button:has-text("Select size")',
                # Radio inputs
                'input[type="radio"][name*="option"]',
                'input[type="radio"][name*="Size"]',
                'input[type="radio"][name*="Color"]',
                # Variant buttons with data attributes
                'button[data-variant]',
                'button[data-option-value]',
                # Labels (often wrap hidden radios)
                'label[for*="variant-"]',
                'label[for*="option-"]',
            ]
            
            for direct_pattern in direct_patterns:
                try:
                    options = page.locator(direct_pattern)
                    option_count = await options.count()
                    
                    if option_count == 0 or option_count > 50:  # Skip if none or too many
                        continue
                    
                    print(f"    Found {option_count} variant options: {direct_pattern}")
                    
                    # Try to click first available
                    for opt_idx in range(min(option_count, 10)):
                        try:
                            option = options.nth(opt_idx)
                            
                            if not await option.is_visible(timeout=500):
                                continue
                            
                            # Check if disabled
                            classes = await option.get_attribute('class') or ''
                            disabled_attr = await option.get_attribute('disabled')
                            
                            if disabled_attr is not None or 'disabled' in classes.lower():
                                continue
                            
                            # Get option text
                            option_text = "option"
                            try:
                                option_text = (await option.get_attribute('value') or 
                                             await option.text_content() or 
                                             f"#{opt_idx + 1}")[:20]
                            except:
                                pass
                            
                            print(f"    Selecting: {option_text}")
                            await option.click(timeout=2000, force=False)
                            await page.wait_for_timeout(800)
                            
                            variant_selected = True
                            print(f"    ✓ Variant selected")
                            break
                            
                        except:
                            continue
                    
                    if variant_selected:
                        break
                        
                except:
                    continue
        
        
        # If no variants found, that might be okay (some products don't have variants)
        if not variant_selected:
            print(f"  No variants detected (product may not require variant selection)")
            
            # In debug mode, take a screenshot to see what's on the page
            if self.debug:
                try:
                    await page.screenshot(path=f"debug_no_variants_{page.url.split('/')[-1][:30]}.png")
                    print(f"  Debug: Saved screenshot of page without variants")
                except:
                    pass
        
        return True  # Return True even if no variants (might not be required)
    
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
            
            # Try multiple Cart API formats
            import json
            
            # Execute fetch in browser context (has cookies/session)
            try:
                if self.debug:
                    print(f"  Calling cart API with variant {variant_id}...")
                
                # Execute fetch directly in the page context (like browser console)
                result = await page.evaluate("""
                    async (variantId) => {
                        try {
                            const response = await fetch('/cart/add.js', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    items: [{
                                        id: variantId,
                                        quantity: 1
                                    }]
                                })
                            });
                            
                            const data = await response.json();
                            
                            if (response.ok) {
                                return { success: true, data: data };
                            } else {
                                return { success: false, status: response.status, error: data };
                            }
                        } catch (error) {
                            return { success: false, error: error.message };
                        }
                    }
                """, int(variant_id))
                
                if result.get('success'):
                    print(f"  ✓ Successfully added to cart via API")
                    return True
                else:
                    if self.debug:
                        error_msg = result.get('error', result.get('status', 'Unknown error'))
                        print(f"  Cart API failed: {error_msg}")
            except Exception as e:
                if self.debug:
                    print(f"  Cart API error: {str(e)[:80]}")
            
            # Cart API didn't work - fallback to product page
            print(f"  ℹ️  Cart API not responding, will try product page method")
            return False  # Signal that we need to try another method
                
        except Exception as e:
            print(f"  ✗ Error using Cart API: {str(e)[:80]}")
            return False
    
    async def _find_and_click_add_to_cart_legacy(self, page: Page) -> bool:
        """
        Find and click the 'Add to Cart' button.
        Uses multiple strategies to handle different themes.
        
        Returns:
            True if successfully added to cart
        """
        # First, try to select a variant if needed
        print("  Checking for product variants (size, color, etc.)...")
        await self._select_variant(page)
        
        # Wait a bit for add-to-cart button to appear/enable after variant selection
        await page.wait_for_timeout(1000)
        
        # Try each add to cart pattern
        print(f"  Looking for add to cart button...")
        for i, pattern in enumerate(self.ADD_TO_CART_PATTERNS, 1):
            try:
                button = page.locator(pattern).first
                if await button.count() > 0:
                    # Check if button is visible
                    if await button.is_visible(timeout=2000):
                        # Check if it's enabled (wait up to 3 seconds for it to become enabled)
                        try:
                            # Wait for button to be enabled (important for stores that enable after variant selection)
                            await page.wait_for_timeout(500)
                            is_enabled = await button.is_enabled(timeout=2000)
                            
                            if is_enabled:
                                print(f"  ✓ Found enabled add to cart button (pattern {i}/{len(self.ADD_TO_CART_PATTERNS)})")
                                print(f"    Pattern: {pattern}")
                                
                                # Get button text for confirmation
                                try:
                                    button_text = await button.text_content()
                                    if button_text:
                                        print(f"    Button text: {button_text.strip()[:30]}")
                                except:
                                    pass
                                
                                await button.click(timeout=5000)
                                await page.wait_for_timeout(2000)  # Wait for cart to update
                                print(f"  ✓ Successfully clicked add to cart button")
                                return True
                            else:
                                if i <= 3:
                                    print(f"    Pattern {i}: Button found but disabled")
                        except:
                            if i <= 3:
                                print(f"    Pattern {i}: Button not enabled")
                            continue
            except Exception as e:
                # Log more details about failures
                if i <= 3:  # Only log first few attempts to avoid spam
                    print(f"    Pattern {i} check failed: {str(e)[:50]}")
                continue
        
        print(f"  ✗ Failed to find enabled add to cart button after trying {len(self.ADD_TO_CART_PATTERNS)} patterns")
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
                return False, "Redirected to cart (no items in cart?)"
            elif 'password' in final_url:
                return False, "Store is password protected"
            elif response and response.status == 404:
                return False, "Checkout page returned 404"
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
    
    async def _test_currency_switch(self, page: Page) -> dict:
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
            
            # Find a country with a different expected currency
            target_country = None
            expected_new_currency = None
            initial_expected_currency = self._get_expected_currency(initial_country)
            
            for country in countries:
                if country != initial_country:
                    expected_currency = self._get_expected_currency(country)
                    if expected_currency and expected_currency != initial_expected_currency:
                        target_country = country
                        expected_new_currency = expected_currency
                        print(f"  Will test switching to: {country} (expect {expected_currency})")
                        break
            
            if not target_country:
                print("  All countries use same currency - no switch test needed")
                return result
            
            # Perform the switch
            country_select = page.locator('select[name="countryCode"]').first
            await country_select.select_option(target_country)
            result['switched_country'] = target_country
            result['tested'] = True
            
            # Wait for currency to update (2-3 seconds as per user)
            print("  Waiting for currency to update...")
            await page.wait_for_timeout(3000)
            
            # Check new currency
            new_currency = await self._get_checkout_currency(page)
            result['switched_currency'] = new_currency
            result['country_currency_pairs'][target_country] = new_currency
            
            if new_currency:
                print(f"  After switch: {target_country} → {new_currency}")
                
                if new_currency != initial_currency:
                    result['currency_changed'] = True
                    print(f"  ✅ Currency switched from {initial_currency} to {new_currency}")
                else:
                    print(f"  ❌ Currency stayed as {initial_currency} (expected {expected_new_currency})")
            else:
                print("  Could not detect currency after switch")
            
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
                
                # Step 1: Navigate directly to products.json to get product data AND establish session
                print(f"Loading {base_url}/products.json...")
                await page.goto(f"{base_url}/products.json?limit=10", wait_until="domcontentloaded", timeout=self.timeout)
                await page.wait_for_timeout(1000)
                
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
                        variants = product.get('variants', [])
                        
                        for variant in variants:
                            vid = variant.get('id')
                            available = variant.get('available', False)
                            
                            if available and vid:
                                variant_id = str(vid)
                                product_title = product.get('title', 'Unknown')
                                variant_title = variant.get('title', '')
                                print(f"  ✓ Found available variant:")
                                print(f"    Product: {product_title}")
                                print(f"    Variant: {variant_title}")
                                print(f"    ID: {variant_id}")
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
                
                # Step 3: Add to cart - try API first, fallback to product page if needed
                print("Adding product to cart...")
                added = await self._add_product_to_cart_via_api(page, variant_id, base_url)
                
                if not added:
                    # Cart API failed - fallback to visiting product page and clicking button
                    print("  Falling back to product page method...")
                    if not product_handle:
                        result.error_message = "Could not add product to cart (API failed, no product handle)"
                        return result
                    
                    product_url_full = f"{base_url}/products/{product_handle}?variant={variant_id}"
                    print(f"  Visiting product page: {product_url_full}")
                    
                    try:
                        await page.goto(product_url_full, wait_until="domcontentloaded", timeout=self.timeout)
                        await page.wait_for_timeout(2000)
                        
                        # Close popups with Escape
                        await page.keyboard.press('Escape')
                        await page.wait_for_timeout(500)
                        
                        # Try to click add to cart button
                        added = await self._find_and_click_add_to_cart_legacy(page)
                        
                        if not added:
                            result.error_message = "Could not add product to cart (both API and button click failed)"
                            return result
                    except Exception as e:
                        result.error_message = f"Could not add product to cart: {str(e)[:100]}"
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
                        detected_requests.append(url)
                        if self.debug:
                            print(f"  📡 Detected: {url[:100]}")
                
                # Attach listener before navigation
                page.on('request', handle_request)
                
                # Navigate to checkout
                print("Navigating to checkout...")
                checkout_reached, checkout_error = await self._navigate_to_checkout(page)
                
                if not checkout_reached:
                    result.error_message = f"Could not reach checkout: {checkout_error}"
                    return result
                
                result.reached_checkout = True
                print("Reached checkout page")
                await page.wait_for_timeout(5000)  # Let checkout load and fire network requests
                
                # Step 6: Test currency switching in checkout
                print("Testing currency verification...")
                currency_test = await self._test_currency_switch(page)
                
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
