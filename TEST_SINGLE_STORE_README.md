# Single Store Test Script - Quick Reference

## Why This Exists

When debugging or developing new features, you don't want to wait through multiple stores. This script lets you test **ONE store at a time** for rapid iteration.

## Quick Start

```bash
python test_single_store.py
```

That's it! It will test Allbirds by default (since that's what you're debugging).

## Customizing Your Test

Edit the file `test_single_store.py` and change these lines:

```python
# Line ~50 - Change the store URL
test_store = "https://www.allbirds.com"  # ← Edit this

# Line ~53 - Show/hide browser
show_browser = True  # True = watch it work, False = headless (faster)

# Line ~56 - Debug mode
debug_mode = True  # True = extra logging + screenshots, False = normal
```

## What You Get

### Console Output

Detailed step-by-step output:
```
Visiting https://www.allbirds.com...
Checking for pop-ups on homepage...
  Looking for geolocation pop-ups...
  ✓ Found geolocation element with pattern: [class*="country"]
    Content preview: Select your country United States España...
  Clicking button: button:has-text("Continue")
  Geolocation action: stayed_on_current_store
Finding a product...
  Trying /collections/all...
  /collections/all failed: HTTP 404
  Trying homepage for products...
  Found product via homepage
Found product: https://www.allbirds.com/products/mens-wool-runners
Adding product to cart...
  Found add to cart button (pattern 1/8): button[name="add"]
  Successfully clicked add to cart button
```

### Debug Screenshots (when debug_mode=True)

Screenshots saved automatically:
- `debug_homepage_www.allbirds.com.png` - Homepage after pop-up handling

### Final Results Summary

```
======================================================================
RESULTS
======================================================================

SUCCESS

--- Currency Detection ---
Currency selector found: True
Multiple currencies supported: True
Detected currencies: ['USD', 'EUR', 'GBP']
Homepage currency: USD
Checkout currency: USD

--- Post-Purchase Upsells ---
Detected: True
Details: Indicators found: upsell, reconvert

--- Debug Info ---
Product URL: https://www.allbirds.com/products/mens-wool-runners
Reached checkout: True
```

## Testing Different Stores

### Quick Test Loop

```bash
# Test Store 1
# Edit test_store = "https://store1.com"
python test_single_store.py

# Test Store 2
# Edit test_store = "https://store2.com"
python test_single_store.py

# Test Store 3
# Edit test_store = "https://store3.com"
python test_single_store.py
```

### Common Test Stores

```python
# Newsletter pop-up issues
test_store = "https://weareplufl.com"

# Geolocation pop-up
test_store = "https://www.allbirds.com"

# No /collections/all
test_store = "https://www.bombas.com"

# Your own store
test_store = "https://yourstore.myshopify.com"
```

## Debug Mode Features

When `debug_mode = True`:

1. **Extra logging**: Shows every pattern checked for geolocation pop-ups
2. **Screenshots**: Saves PNG files for debugging
3. **Element detection**: Shows what text content was found in pop-ups
4. **Pattern failures**: Shows why certain patterns didn't match

## Settings Summary

| Setting | Default | What it does |
|---------|---------|--------------|
| `test_store` | allbirds.com | The store to test |
| `show_browser` | True | Show browser window (False = headless) |
| `debug_mode` | True | Extra logging and screenshots |

## Workflow for Fixing Issues

1. **Run test**: `python test_single_store.py`
2. **Watch browser**: See where it gets stuck
3. **Check console**: Look for error messages
4. **Check screenshot**: See what the page looks like
5. **Edit code**: Fix the issue in `shopify_verifier.py`
6. **Repeat**: Run test again immediately

No need to test 3 stores, no need to wait through batch processing!

## Viewport Size

Browser window is now **1280x800** (was 1920x1080), so it should fit on your screen.

## Example Debug Output

Here's what you'll see with Allbirds geolocation issue:

```
Checking for pop-ups on homepage...
  Looking for geolocation pop-ups...
  ✓ Found geolocation element with pattern: [class*="country"]
    Content preview: Select your country United States España Canada...
  Clicking button: button:has-text("Continue")
  Geolocation action: stayed_on_current_store
```

or if it fails:

```
Checking for pop-ups on homepage...
  Looking for geolocation pop-ups...
  ✓ Found geolocation element with pattern: [class*="country"]
    Content preview: Select your country United States España Canada...
    Pattern 0 check failed: Timeout 1000ms exceeded
    Pattern 1 check failed: Timeout 1000ms exceeded
  No 'continue' button found, trying generic close...
  Found pop-up close button: button[aria-label*="close" i]
  Closed pop-up #1
```

## Tips

- **Start with show_browser=True**: Watch what's happening
- **Use debug_mode=True**: Get detailed logs
- **Check screenshots**: Visual confirmation of state
- **Focus on one issue**: Fix geolocation, then test add-to-cart, etc.

## When to Use vs quick_start.py

| Use test_single_store.py | Use quick_start.py |
|--------------------------|-------------------|
| Debugging specific store | Testing overall functionality |
| Rapid iteration | Final verification |
| Developing new features | Smoke testing |
| Investigating failures | Checking multiple stores |
| **Fast feedback loop** | **Comprehensive testing** |

---

**Current focus**: Testing Allbirds geolocation pop-up handling
**Run**: `python test_single_store.py`
**Edit store**: Line ~50 in `test_single_store.py`
