# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-01-15

### Major Performance Optimization

**Complete verification flow redesign for maximum speed and reliability.**

#### What Changed

**OLD FLOW (Slow, Complex):**
1. Load homepage → Wait for render
2. Close pop-ups (newsletter, cookies, geolocation)
3. Find product links or navigate to `/collections/all`
4. Navigate to product page → Wait for render
5. Close more pop-ups
6. Select variants (size, color) by clicking UI elements
7. Click "Add to Cart" button
8. Navigate to checkout

**NEW FLOW (Fast, Direct):**
1. Load `/products.json?limit=10` → Get product data + establish session
2. Add to cart via Shopify Cart API (`/cart/add.js`)
3. Navigate to `/checkout`

**Result:** **10-15 seconds** per store (was 30-60 seconds)

#### Technical Changes

**Removed (No Longer Needed):**
- ❌ Pop-up handling system (58 lines)
- ❌ Homepage navigation and rendering
- ❌ Product page UI interaction
- ❌ Variant selection via clicking buttons/swatches
- ❌ "Add to Cart" button finding and clicking
- ❌ Collection page navigation
- ❌ Geolocation pop-up handling

**Added:**
- ✅ Direct `/products.json` loading via browser context
- ✅ Cart API integration using `page.evaluate()` with `fetch()`
- ✅ Intelligent country-to-currency mapping for multi-currency testing
- ✅ Network request monitoring for post-purchase detection
- ✅ In-checkout currency switching verification

**Kept (Fallback Only):**
- Legacy add-to-cart button clicking (used only if Cart API fails)
- Variant selection via UI (used only in fallback path)
- Simple Escape key press (no complex pop-up handling)

#### Performance Improvements

- **Speed**: 3-4x faster (10-15s vs 30-60s per store)
- **Reliability**: Fewer points of failure (3 steps vs 8+ steps)
- **Code Size**: 33% reduction (1,749 → 1,169 lines)
- **Headless Mode**: Works perfectly in headless (no UI interaction needed)

#### Verification Accuracy Improvements

**Currency Detection:**
- Now tests actual currency switching in checkout
- Uses country selector to change currency
- Verifies prices update to new currency
- Handles Euro zone correctly (multiple countries, same currency)

**Post-Purchase Detection:**
- Monitors network requests for post-purchase app loads
- Filters out survey/feedback apps (e.g., TripleWhale)
- Extracts app name from request URLs
- More accurate detection (network events vs HTML indicators)

### Breaking Changes

None! All existing scripts and result formats remain compatible.

## [1.0.0] - 2026-01-15

### Added
- Initial release
- Core verification engine for Shopify stores
- Multi-currency support detection
- Post-purchase upsell detection
- Batch processing with progress tracking
- Results analysis tools
- Comprehensive documentation
