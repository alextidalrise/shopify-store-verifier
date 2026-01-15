# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - 2026-01-15

#### Pop-up Handling System
- **Automatic pop-up detection and closing**: Added robust system to detect and close various types of pop-ups that commonly block Shopify store interactions
- **Multiple pop-up types supported**:
  - Newsletter sign-up modals
  - Cookie consent banners
  - Age verification pop-ups
  - Promotional pop-ups
  - Geolocation/country selector pop-ups
  
- **Smart closing strategies**:
  - Tries multiple close button patterns (X, "No thanks", "Maybe later", etc.)
  - Presses Escape key as fallback
  - Handles backdrop-dismiss modals
  - Retries add-to-cart if pop-ups were blocking it

- **Geolocation pop-up handling**: Special handling for country/currency selector pop-ups:
  - Detects "shop in your currency" prompts
  - Looks for "Continue to current site" / "Stay here" buttons
  - Avoids redirecting to different stores/locales
  - Logs actions taken for debugging

#### Enhanced Logging
- **Detailed product discovery logging**: Shows which strategy found the product
- **Add-to-cart pattern logging**: Shows which button pattern succeeded
- **Pop-up closure logging**: Reports when pop-ups are detected and closed
- **Error details**: More descriptive error messages for debugging

#### Strategic Pop-up Closing
Pop-ups are now automatically closed at key points:
1. After landing on homepage
2. When searching for products (collections/all, homepage)
3. After navigating to product page
4. Before attempting to add to cart
5. Retry mechanism if add-to-cart fails due to pop-ups

### Technical Details

**New Methods:**
- `_close_popups()`: Main pop-up detection and closing method
- `_handle_geolocation_popup()`: Special handler for country/currency selector pop-ups

**New Class Variables:**
- `POPUP_CLOSE_PATTERNS`: 20+ patterns for close buttons across different pop-up types
- `POPUP_OVERLAY_PATTERNS`: Patterns for detecting modal/overlay containers

**Updated Methods:**
- `verify_store()`: Now calls pop-up handlers at strategic points
- `_find_product_page()`: Added pop-up closing when navigating to collections/homepage
- `_find_and_click_add_to_cart()`: Enhanced logging and retry logic

### Impact

**Expected Improvements:**
- **Higher success rate**: Many failures were due to pop-ups blocking interactions
- **Better handling of real-world stores**: Most production stores have newsletter or cookie pop-ups
- **Geolocation awareness**: Can now handle multi-market stores that prompt for country selection

**What's Fixed:**
- ✅ Newsletter pop-ups blocking the entire screen
- ✅ Cookie consent banners blocking add-to-cart buttons
- ✅ Geolocation pop-ups asking to redirect to different stores
- ✅ Multiple stacked pop-ups (tries up to 3 times)
- ✅ Add-to-cart failures now retry after clearing pop-ups

## [1.0.0] - 2026-01-15

### Added
- Initial release
- Core verification engine for Shopify stores
- Multi-currency support detection
- Post-purchase upsell detection
- Batch processing with progress tracking
- Results analysis tools
- Comprehensive documentation
