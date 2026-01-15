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
    POPUP_CLOSE_PATTERNS = [
        # Generic close buttons
        'button[aria-label*="close" i]',
        'button[title*="close" i]',
        '[class*="close"]',
        '[id*="close"]',
        '[data-dismiss]',
        '[aria-label*="dismiss" i]',
        # X buttons
        'button:has-text("×")',
        'button:has-text("✕")',
        '[class*="modal"] button:has-text("×")',
        # No thanks / decline buttons (for newsletters, etc.)
        'button:has-text("No thanks")',
        'button:has-text("No, thanks")',
        'button:has-text("Maybe later")',
        'button:has-text("Not now")',
        'button:has-text("Skip")',
        'button:has-text("Continue to site")',
        'a:has-text("Continue to site")',
        # Cookie consent
        'button:has-text("Accept")',
        'button:has-text("I agree")',
        'button:has-text("Got it")',
        'button:has-text("OK")',
        '[id*="cookie"] button',
        '[class*="cookie"] button',
        # Age verification
        'button:has-text("Yes")',
        'button:has-text("Enter")',
        'button:has-text("I am")',
    ]
    
    # Pop-up modal/overlay patterns
    POPUP_OVERLAY_PATTERNS = [
        '[class*="modal"]',
        '[class*="popup"]',
        '[class*="overlay"]',
        '[role="dialog"]',
        '[class*="newsletter"]',
        '[id*="popup"]',
        '[id*="modal"]',
        '[data-modal]',
        # Geolocation/country selector pop-ups
        '[class*="geolocation-popup"]',
        '[class*="country-popup"]',
        '[class*="locale-popup"]',
    ]
    
    # Common selectors for currency switchers (various themes)
    CURRENCY_SELECTOR_PATTERNS = [
        # Generic patterns
        '[data-currency-selector]',
        '[class*="currency-selector"]',
        '[class*="currency-picker"]',
        '[id*="currency-selector"]',
        '[id*="currency-picker"]',
        # Geolocation bar
        '[class*="geolocation"]',
        '[class*="country-selector"]',
        '[data-localization-form]',
        'localization-form',
        # Dropdown patterns
        'select[name="country_code"]',
        'select[name*="currency"]',
        # Button patterns
        'button[aria-label*="currency" i]',
        'button[aria-label*="country" i]',
    ]
    
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
    
    async def _close_popups(self, page: Page, max_attempts: int = 3) -> int:
        """
        Detect and close pop-ups on the page.
        
        This method tries multiple strategies:
        1. Look for close buttons (X, "No thanks", etc.)
        2. Press Escape key
        3. Click outside modals if they have backdrop-dismiss
        
        Args:
            page: Playwright page object
            max_attempts: Maximum number of pop-ups to try closing
            
        Returns:
            Number of pop-ups closed
        """
        closed_count = 0
        
        for attempt in range(max_attempts):
            await page.wait_for_timeout(1000)  # Let any pop-ups render
            
            # Strategy 1: Try to find and click close buttons
            for pattern in self.POPUP_CLOSE_PATTERNS:
                try:
                    # Look for visible close buttons
                    close_button = page.locator(pattern).first
                    if await close_button.count() > 0:
                        if await close_button.is_visible(timeout=2000):
                            print(f"  Found pop-up close button: {pattern}")
                            await close_button.click(timeout=3000)
                            await page.wait_for_timeout(500)
                            closed_count += 1
                            print(f"  Closed pop-up #{closed_count}")
                            break  # Try again for more pop-ups
                except Exception as e:
                    continue
            else:
                # Strategy 2: Try pressing Escape key
                try:
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(500)
                    
                    # Check if a modal disappeared
                    has_modal = False
                    for overlay_pattern in self.POPUP_OVERLAY_PATTERNS[:5]:
                        try:
                            if await page.locator(overlay_pattern).first.is_visible(timeout=1000):
                                has_modal = True
                                break
                        except:
                            continue
                    
                    if not has_modal:
                        # No more visible modals, we're done
                        break
                except:
                    pass
                
                # No more pop-ups found
                break
        
        if closed_count > 0:
            print(f"  Total pop-ups closed: {closed_count}")
            await page.wait_for_timeout(1000)  # Wait for any animations
        
        return closed_count
    
    async def _handle_geolocation_popup(self, page: Page, debug: bool = True) -> Optional[str]:
        """
        Handle geolocation/country selector pop-ups.
        
        These pop-ups ask users to select their country/region, and may redirect
        to different stores, subdomains, or locale paths.
        
        For now, we'll try to:
        1. Detect if there's a geolocation pop-up
        2. Look for "Continue to current site" or "Stay here" type buttons
        3. If we find country-specific options, note them but decline
        
        Returns:
            The action taken or None
        """
        try:
            # Look for geolocation-specific pop-ups
            geolocation_patterns = [
                '[class*="geolocation"]',
                '[class*="country-selector"]',
                '[class*="locale-selector"]',
                '[class*="region-selector"]',
                '[class*="country"]',
                '[class*="CountrySelector"]',
                '[class*="location"]',
                '[id*="country"]',
                '[id*="location"]',
                '[id*="locale"]',
                'text=/shop.*currency/i',
                'text=/country.*store/i',
                'text=/select.*country/i',
                'text=/shipping.*to/i',
            ]
            
            if debug:
                print(f"  Looking for geolocation pop-ups...")
            
            found_geo_element = False
            
            for i, pattern in enumerate(geolocation_patterns):
                try:
                    element = page.locator(pattern).first
                    count = await element.count()
                    if count > 0:
                        is_visible = await element.is_visible(timeout=1000)
                        if is_visible:
                            if debug:
                                print(f"  ✓ Found geolocation element with pattern: {pattern}")
                            found_geo_element = True
                            
                            # Try to get text content for debugging
                            try:
                                text_content = await element.text_content()
                                if text_content and debug:
                                    preview = text_content[:100].replace('\n', ' ')
                                    print(f"    Content preview: {preview}...")
                            except:
                                pass
                            
                            # Look for "stay here" / "continue" buttons
                            continue_patterns = [
                                'button:has-text("Continue")',
                                'button:has-text("Stay")',
                                'button:has-text("No")',
                                'button:has-text("Keep shopping")',
                                'button:has-text("Continue shopping")',
                                'button:has-text("No thanks")',
                                'a:has-text("Continue")',
                                'a:has-text("Stay")',
                                'a:has-text("No thanks")',
                                # Close button patterns
                                'button[aria-label*="close" i]',
                                '[class*="close"]',
                            ]
                            
                            for continue_pattern in continue_patterns:
                                try:
                                    continue_btn = page.locator(continue_pattern).first
                                    if await continue_btn.count() > 0 and await continue_btn.is_visible(timeout=1000):
                                        print(f"  Clicking button: {continue_pattern}")
                                        await continue_btn.click(timeout=3000)
                                        await page.wait_for_timeout(1000)
                                        return "stayed_on_current_store"
                                except:
                                    continue
                            
                            # If no continue button found, try to close it
                            print(f"  No 'continue' button found, trying generic close...")
                            await self._close_popups(page, max_attempts=1)
                            return "closed_geolocation_popup"
                        
                except Exception as e:
                    if debug and i < 5:  # Only show first few errors
                        print(f"    Pattern {i} check failed: {str(e)[:50]}")
                    continue
            
            if not found_geo_element and debug:
                print(f"  No geolocation pop-ups detected")
                    
        except Exception as e:
            if debug:
                print(f"  Geolocation check error: {str(e)[:80]}")
        
        return None
    
    async def _detect_currency_from_page(self, page: Page) -> Optional[str]:
        """
        Detect currency from page content (price displays, JSON data, etc).
        
        Returns:
            Currency code (e.g., 'USD', 'GBP') or None
        """
        try:
            # Try to get currency from Shopify JS objects
            currency = await page.evaluate("""() => {
                // Check various Shopify objects
                if (typeof Shopify !== 'undefined') {
                    if (Shopify.currency && Shopify.currency.active) {
                        return Shopify.currency.active;
                    }
                    if (Shopify.Checkout && Shopify.Checkout.currency) {
                        return Shopify.Checkout.currency;
                    }
                }
                
                // Check window objects
                if (window.theme && window.theme.moneyFormat) {
                    const match = window.theme.moneyFormat.match(/[A-Z]{3}/);
                    if (match) return match[0];
                }
                
                // Check meta tags
                const currencyMeta = document.querySelector('meta[property="og:price:currency"]');
                if (currencyMeta) return currencyMeta.getAttribute('content');
                
                return null;
            }""")
            
            if currency:
                return currency.upper()
            
            # Fallback: parse from visible price text
            prices = await page.locator('[class*="price"], [data-price]').all_text_contents()
            for price_text in prices[:5]:  # Check first few prices
                # Look for currency symbols or codes
                match = re.search(r'\b([A-Z]{3})\b', price_text)
                if match:
                    return match.group(1)
                
        except Exception as e:
            print(f"Error detecting currency: {e}")
        
        return None
    
    async def _check_currency_selector(self, page: Page) -> tuple[bool, list[str]]:
        """
        Check if page has a currency selector and detect available currencies.
        
        Returns:
            Tuple of (selector_found, list_of_currencies)
        """
        detected_currencies = []
        
        for selector in self.CURRENCY_SELECTOR_PATTERNS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0 and await element.is_visible(timeout=2000):
                    # Try to get available options
                    try:
                        # For select dropdowns
                        if 'select' in selector:
                            options = await element.locator('option').all_text_contents()
                            for opt in options:
                                # Extract currency codes
                                match = re.search(r'\b([A-Z]{3})\b', opt)
                                if match:
                                    detected_currencies.append(match.group(1))
                        else:
                            # For other elements, check text content
                            text = await element.text_content()
                            if text:
                                currencies = re.findall(r'\b([A-Z]{3})\b', text)
                                detected_currencies.extend(currencies)
                    except:
                        pass
                    
                    return True, list(set(detected_currencies))
            except:
                continue
        
        return False, []
    
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
    
    async def _find_and_click_add_to_cart(self, page: Page) -> bool:
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
    
    async def _find_product_page(self, page: Page, base_url: str) -> Optional[str]:
        """
        Find a product page to test with.
        
        Returns:
            Product URL or None
        """
        # Strategy 1: Try /collections/all
        try:
            print("  Trying /collections/all...")
            await page.goto(f"{base_url}/collections/all", wait_until="domcontentloaded", timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Close any pop-ups that might appear
            await self._close_popups(page, max_attempts=1)
            
            # Find first product link
            product_links = page.locator('a[href*="/products/"]')
            count = await product_links.count()
            if count > 0:
                href = await product_links.first.get_attribute('href')
                if href:
                    if href.startswith('http'):
                        return href
                    return base_url + href if href.startswith('/') else base_url + '/' + href
            print("  No products found in /collections/all")
        except Exception as e:
            print(f"  /collections/all failed: {str(e)[:50]}")
            pass
        
        # Strategy 2: Try homepage
        try:
            print("  Trying homepage for products...")
            await page.goto(base_url, wait_until="domcontentloaded", timeout=self.timeout)
            await page.wait_for_timeout(2000)
            
            # Close any pop-ups
            await self._close_popups(page, max_attempts=1)
            
            product_links = page.locator('a[href*="/products/"]')
            count = await product_links.count()
            if count > 0:
                href = await product_links.first.get_attribute('href')
                if href:
                    if href.startswith('http'):
                        return href
                    return base_url + href if href.startswith('/') else base_url + '/' + href
            print("  No products found on homepage")
        except Exception as e:
            print(f"  Homepage search failed: {str(e)[:50]}")
            pass
        
        # Strategy 3: Use products.json API
        try:
            print("  Trying products.json API...")
            response = await page.request.get(f"{base_url}/products.json?limit=1")
            if response.ok:
                data = await response.json()
                if data.get('products') and len(data['products']) > 0:
                    handle = data['products'][0].get('handle')
                    if handle:
                        print(f"  Found product via API: {handle}")
                        return f"{base_url}/products/{handle}"
                print("  No products found in API response")
            else:
                print(f"  API request failed with status {response.status}")
        except Exception as e:
            print(f"  API request failed: {str(e)[:50]}")
            pass
        
        print("  Could not find any products using any strategy")
        return None
    
    async def _navigate_to_checkout(self, page: Page) -> bool:
        """
        Navigate from cart to checkout.
        
        Returns:
            True if successfully reached checkout
        """
        # Try clicking checkout button
        for pattern in self.CHECKOUT_BUTTON_PATTERNS:
            try:
                button = page.locator(pattern).first
                if await button.count() > 0 and await button.is_visible(timeout=2000):
                    await button.click(timeout=5000)
                    await page.wait_for_timeout(3000)
                    
                    # Check if we're on checkout
                    url = page.url
                    if '/checkout' in url or 'checkout.shopify.com' in url:
                        return True
            except:
                continue
        
        # Direct navigation fallback
        try:
            base_url = self._normalize_url(page.url)
            await page.goto(f"{base_url}/checkout", timeout=self.timeout)
            await page.wait_for_timeout(2000)
            return True
        except:
            pass
        
        return False
    
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
    
    async def _monitor_post_purchase_network(self, page: Page) -> tuple[bool, Optional[str], list[str]]:
        """
        Monitor network requests for post-purchase indicators.
        Looks for:
        1. CDN script loads with 'post-purchase' in URL
        2. App-specific trigger endpoints (ppShouldTrigger, etc.)
        
        Returns:
            Tuple of (detected, app_name, list_of_detected_requests)
        """
        detected_requests = []
        detected_app = None
        
        def handle_request(request):
            url = request.url
            
            # Check for post-purchase patterns
            if 'post-purchase' in url.lower() or 'post_purchase' in url.lower():
                detected_requests.append(url)
                
                # Try to extract app name from URL
                # Pattern: /post-purchase/version/aftersell-549/
                # Pattern: /post-purchase/handle/post-purchase/version/aftersell-549/
                match = re.search(r'/([a-z]+(?:-[a-z]+)?)-\d+/', url)
                if match:
                    app_name = match.group(1)
                    # Normalize app names
                    app_name_map = {
                        'aftersell': 'AfterSell',
                        'reconvert': 'ReConvert',
                        'zipify': 'Zipify',
                        'carthook': 'CartHook',
                        'honeycomb': 'Honeycomb',
                    }
                    return app_name_map.get(app_name, app_name.title())
            
            # Check for app-specific trigger endpoints
            trigger_patterns = [
                ('ppShouldTrigger', 'aftersell'),
                ('shouldTrigger', 'reconvert'),
                ('trigger-check', 'generic'),
            ]
            
            for pattern, app in trigger_patterns:
                if pattern in url:
                    detected_requests.append(url)
                    if app != 'generic':
                        return app.title()
        
        # Set up network monitoring
        page.on('request', lambda req: handle_request(req) or None)
        page.on('response', lambda res: handle_request(res.request) or None)
        
        # Wait for network activity
        await page.wait_for_timeout(5000)
        
        # Analyze detected requests to extract app name
        if detected_requests:
            for url in detected_requests:
                # Try multiple patterns
                patterns = [
                    r'/([a-z]+(?:-[a-z]+)?)-\d+/',  # aftersell-549
                    r'//([a-z]+)\.(?:app|io|com)/',  # aftersell.app
                    r'/post-purchase/[^/]+/([a-z]+)',  # /post-purchase/handle/aftersell
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, url.lower())
                    if match:
                        app_raw = match.group(1)
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
        
        return len(detected_requests) > 0, detected_app, detected_requests
    
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
                
                # Step 1: Visit homepage and check for currency selector
                print(f"Visiting {base_url}...")
                await page.goto(base_url, wait_until="domcontentloaded", timeout=self.timeout)
                await page.wait_for_timeout(3000)  # Let page fully load
                
                # Close any pop-ups on homepage (newsletters, cookies, etc.)
                print("Checking for pop-ups on homepage...")
                await self._close_popups(page)
                
                # Handle geolocation/country selector pop-ups
                geo_action = await self._handle_geolocation_popup(page, debug=self.debug)
                if geo_action:
                    print(f"  Geolocation action: {geo_action}")
                
                # Take a screenshot if in debug mode
                if self.debug:
                    try:
                        await page.screenshot(path=f"debug_homepage_{base_url.replace('https://', '').replace('/', '_')}.png")
                        print(f"  Debug: Screenshot saved")
                    except:
                        pass
                
                # Step 2: Find a product
                print("Finding a product...")
                product_url = await self._find_product_page(page, base_url)
                
                if not product_url:
                    result.error_message = "Could not find any product page"
                    return result
                
                result.product_url = product_url
                print(f"Found product: {product_url}")
                
                # Step 3: Go to product page
                await page.goto(product_url, wait_until="domcontentloaded", timeout=self.timeout)
                await page.wait_for_timeout(2000)
                
                # Close any pop-ups on product page
                print("Checking for pop-ups on product page...")
                
                # Try Escape key first (works for many modal-style popups including geolocation)
                try:
                    await page.keyboard.press('Escape')
                    await page.wait_for_timeout(500)
                    print("  Pressed Escape key to dismiss any modal popups")
                except:
                    pass
                
                await self._close_popups(page)
                
                # Step 4: Add to cart
                print("Adding product to cart...")
                added = await self._find_and_click_add_to_cart(page)
                
                # If add to cart failed, try closing pop-ups and retry once
                if not added:
                    print("Add to cart failed, checking for blocking pop-ups...")
                    closed = await self._close_popups(page, max_attempts=2)
                    if closed > 0:
                        print("Retrying add to cart after closing pop-ups...")
                        await page.wait_for_timeout(1000)
                        added = await self._find_and_click_add_to_cart(page)
                
                if not added:
                    result.error_message = "Could not add product to cart"
                    return result
                
                print("Product added to cart")
                
                # Step 5: Set up network monitoring BEFORE navigating to checkout
                print("Setting up post-purchase monitoring...")
                detected_requests = []
                
                def handle_request(request):
                    url = request.url
                    # Check for post-purchase patterns
                    if 'post-purchase' in url.lower() or 'post_purchase' in url.lower() or 'ppShouldTrigger' in url:
                        detected_requests.append(url)
                        if self.debug:
                            print(f"  📡 Detected: {url[:100]}")
                
                # Attach listener before navigation
                page.on('request', handle_request)
                
                # Navigate to checkout
                print("Navigating to checkout...")
                checkout_reached = await self._navigate_to_checkout(page)
                
                if not checkout_reached:
                    result.error_message = "Could not reach checkout page"
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
                    for url in detected_requests:
                        # Try multiple patterns to extract app name
                        patterns = [
                            r'/([a-z]+(?:-[a-z]+)?)-\d+/',  # aftersell-549
                            r'//([a-z]+)\.(?:app|io|com)/',  # aftersell.app
                            r'/post-purchase/[^/]+/([a-z]+)',  # /post-purchase/handle/aftersell
                        ]
                        
                        for pattern in patterns:
                            match = re.search(pattern, url.lower())
                            if match:
                                app_raw = match.group(1)
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
    print(f"  - Currency selector found: {result.currency_selector_found}")
    print(f"  - Multiple currencies: {result.multiple_currencies_supported}")
    print(f"  - Detected currencies: {result.detected_currencies}")
    print(f"  - Homepage currency: {result.homepage_currency}")
    print(f"  - Checkout currency: {result.checkout_currency}")
    print(f"\nPost-Purchase Upsells:")
    print(f"  - Detected: {result.post_purchase_upsell_detected}")
    print(f"  - Details: {result.post_purchase_details}")
    print(f"\nDebug Info:")
    print(f"  - Product URL: {result.product_url}")
    print(f"  - Reached checkout: {result.reached_checkout}")
    
    # Save to JSON
    with open('verification_result.json', 'w') as f:
        json.dump(result.to_dict(), f, indent=2)
    print(f"\nResults saved to verification_result.json")


if __name__ == "__main__":
    asyncio.run(main())
