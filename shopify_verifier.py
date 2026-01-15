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
    
    # Currency verification
    multiple_currencies_supported: bool = False
    currency_selector_found: bool = False
    detected_currencies: list[str] = None
    checkout_currency: Optional[str] = None
    homepage_currency: Optional[str] = None
    
    # Post-purchase verification
    post_purchase_upsell_detected: bool = False
    post_purchase_details: Optional[str] = None
    
    # Debug info
    product_url: Optional[str] = None
    reached_checkout: bool = False
    
    def __post_init__(self):
        if self.detected_currencies is None:
            self.detected_currencies = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "store_url": self.store_url,
            "success": self.success,
            "error_message": self.error_message,
            "multiple_currencies_supported": self.multiple_currencies_supported,
            "currency_selector_found": self.currency_selector_found,
            "detected_currencies": self.detected_currencies,
            "checkout_currency": self.checkout_currency,
            "homepage_currency": self.homepage_currency,
            "post_purchase_upsell_detected": self.post_purchase_upsell_detected,
            "post_purchase_details": self.post_purchase_details,
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
                # Generic buttons in product forms (very permissive)
                'form button[type="button"]:not([aria-label*="close" i])',
                'div[class*="size"] button',
                'div[class*="Size"] button',
                # Allbirds-style: buttons that are siblings to each other
                'button ~ button',  # Any button that has a button sibling (likely part of a button group)
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
        
        # Strategy 4: Ultra-aggressive - find ANY button that might be a size/variant
        # Look for buttons with size-like text (numbers, S/M/L, etc.)
        if not variant_selected:
            print(f"  Direct search didn't work, trying ultra-aggressive search...")
            
            try:
                # Get ALL buttons on the page
                all_buttons = page.locator('button')
                button_count = await all_buttons.count()
                
                print(f"    Found {button_count} total buttons on page")
                
                # Look through buttons for ones that look like sizes/variants
                for idx in range(min(button_count, 100)):  # Check up to 100 buttons
                    try:
                        btn = all_buttons.nth(idx)
                        
                        if not await btn.is_visible(timeout=200):
                            continue
                        
                        # Get button text
                        btn_text = await btn.text_content()
                        if not btn_text:
                            continue
                        
                        btn_text = btn_text.strip()
                        
                        # Skip empty or very long text (likely not a variant)
                        if not btn_text or len(btn_text) > 10:
                            continue
                        
                        # Check if button text looks like a size or variant
                        # Sizes: "8", "8.5", "S", "M", "L", "XL", "Red", etc.
                        looks_like_variant = (
                            btn_text.replace('.', '').replace('½', '').isdigit() or  # "8", "8.5", "10½"
                            btn_text in ['S', 'M', 'L', 'XL', 'XXL', 'XXXL', 'XS'] or  # Clothing sizes
                            (len(btn_text) <= 5 and btn_text.isalpha())  # Short text like "Red", "Blue"
                        )
                        
                        if not looks_like_variant:
                            continue
                        
                        # Check if disabled
                        disabled = await btn.get_attribute('disabled')
                        classes = await btn.get_attribute('class') or ''
                        
                        if disabled is not None:
                            continue
                        
                        # If sold out in classes, skip
                        if 'sold-out' in classes.lower() or 'disabled' in classes.lower():
                            continue
                        
                        print(f"    Found potential variant button: '{btn_text}'")
                        
                        # Try to click it
                        try:
                            await btn.click(timeout=2000, force=False)
                            await page.wait_for_timeout(800)
                            variant_selected = True
                            print(f"    ✓ Clicked variant button: '{btn_text}'")
                            break
                        except Exception as e:
                            print(f"    Failed to click '{btn_text}': {str(e)[:30]}")
                            continue
                            
                    except:
                        continue
                        
            except Exception as e:
                print(f"    Ultra-aggressive search failed: {str(e)[:50]}")
        
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
    
    async def _detect_post_purchase_upsell(self, page: Page) -> tuple[bool, Optional[str]]:
        """
        Detect if there's a post-purchase upsell flow.
        This is tricky because we need to complete the checkout, which we can't do fully.
        We'll look for indicators instead.
        
        Returns:
            Tuple of (detected, details)
        """
        try:
            # Check page content for post-purchase app indicators
            content = await page.content()
            
            # Common post-purchase app identifiers
            post_purchase_indicators = [
                'post-purchase',
                'post_purchase',
                'postpurchase',
                'reconvert',
                'zipify',
                'upsell',
                'one-click-upsell',
                'aftersell',
                'carthook',
            ]
            
            content_lower = content.lower()
            detected_indicators = []
            
            for indicator in post_purchase_indicators:
                if indicator in content_lower:
                    detected_indicators.append(indicator)
            
            # Check for Shopify scripts API (used by post-purchase apps)
            has_scripts_api = 'shopify.analytics.publish' in content or 'post_purchase' in content
            
            # Check for specific app domains/CDNs
            app_domains = [
                'reconvert.io',
                'zipify.com',
                'carthook.com',
                'aftersell.com',
            ]
            
            for domain in app_domains:
                if domain in content:
                    detected_indicators.append(f"app:{domain}")
            
            if detected_indicators or has_scripts_api:
                details = f"Indicators found: {', '.join(detected_indicators[:3])}"
                return True, details
            
            return False, None
            
        except Exception as e:
            return False, f"Error: {str(e)}"
    
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
                
                # Detect homepage currency
                result.homepage_currency = await self._detect_currency_from_page(page)
                
                # Check for currency selector
                selector_found, currencies = await self._check_currency_selector(page)
                result.currency_selector_found = selector_found
                result.detected_currencies = currencies
                result.multiple_currencies_supported = len(currencies) > 1
                
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
                
                # Step 5: Navigate to checkout
                print("Navigating to checkout...")
                checkout_reached = await self._navigate_to_checkout(page)
                
                if not checkout_reached:
                    result.error_message = "Could not reach checkout page"
                    return result
                
                result.reached_checkout = True
                print("Reached checkout page")
                await page.wait_for_timeout(3000)  # Let checkout load
                
                # Step 6: Detect currency in checkout
                result.checkout_currency = await self._detect_currency_from_page(page)
                
                # Step 7: Check for post-purchase upsell indicators
                print("Checking for post-purchase upsells...")
                upsell_detected, upsell_details = await self._detect_post_purchase_upsell(page)
                result.post_purchase_upsell_detected = upsell_detected
                result.post_purchase_details = upsell_details
                
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
