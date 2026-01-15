# Debug Fix - Container Selection Issue

## Problem Identified

From the test output:
```
Found 120 variant container(s): div[class*="option"]
No variants detected (product may not require variant selection)
```

**Root Cause**:
1. `div[class*="option"]` pattern was **too broad** - matched 120 elements (newsletter options, footer options, etc.)
2. Code only checked **first 5 containers** (line: `range(min(container_count, 5))`)
3. Those first 5 weren't actual variant containers - they didn't have clickable size/color buttons
4. Result: No variants selected → Add-to-cart stayed disabled

## Fixes Applied

### Fix 1: Skip Overly Broad Matches
```python
# Don't process if we found way too many (likely false matches)
if container_count > 20:
    print(f"  Skipping {container_pattern}: found {container_count} (too many)")
    continue
```

**Effect**: The 120 containers with `div[class*="option"]` will be skipped

### Fix 2: Reordered Container Patterns (Most Specific First)
```python
container_patterns = [
    'fieldset',                           # Semantic HTML (best)
    '[role="radiogroup"]',                # ARIA role
    'div[data-product-option]',           # Data attributes (specific)
    'div[class*="ProductOption"]',        # Shopify-specific
    'div[class*="product-form__input"]',
    'div[class*="variant-selector"]',     # More specific than just "variant"
    'div[class*="product-variant"]',      # More specific
]
```

**Removed**: Generic `div[class*="variant"]` and `div[class*="option"]` - too broad

### Fix 3: Added Direct Search Fallback (Strategy 3)
If container approach fails, search for variant elements directly:

```python
direct_patterns = [
    'input[type="radio"][name*="option"]',    # Direct radio search
    'input[type="radio"][name*="Size"]',
    'input[type="radio"][name*="Color"]',
    'button[data-variant]',
    'label[for*="variant-"]',
    'label[for*="option-"]',
]
```

**Effect**: Even if containers aren't found, we still try to find variant buttons/radios

### Fix 4: Scroll to Variants
```python
# Scroll down a bit to ensure variant selectors are in view
await page.evaluate("window.scrollBy(0, 300)")
```

**Effect**: Ensures size selector isn't off-screen

### Fix 5: Debug Screenshot
```python
if not variant_selected and self.debug:
    await page.screenshot(path=f"debug_no_variants_*.png")
```

**Effect**: Save screenshot when variants aren't found for debugging

### Fix 6: Increased Container Check Limit
```python
# From: range(min(container_count, 5))
# To:   range(min(container_count, 10))
```

**Effect**: Check up to 10 containers instead of 5 (in case first few aren't the right ones)

## Expected New Output

```
Checking for product variants (size, color, etc.)...
  Found 2 potential variant container(s): fieldset
    Variant group: Size
      Found 7 options (button:not([disabled]))
        Selecting: 10
        ✓ Variant selected
Looking for add to cart button...
  ✓ Found enabled add to cart button
```

Or with fallback:
```
Checking for product variants (size, color, etc.)...
  Found 120 potential variant container(s): div[class*="option"]
  Skipping div[class*="option"]: found 120 (too many, likely false matches)
  Container approach didn't find variants, trying direct search...
    Found 7 variant options: input[type="radio"][name*="option"]
    Selecting: 10
    ✓ Variant selected
```

## Test Again

Run:
```bash
python test_single_store.py
```

**What to watch for**:
1. Should skip the 120 container match
2. Should try fieldset or direct search patterns
3. Should find and click actual size buttons
4. Add-to-cart should become enabled
5. If still fails, check the debug screenshot: `debug_no_variants_*.png`

## Why This Is Better

**Before**:
- ❌ Matched 120 irrelevant containers
- ❌ Only checked first 5 (which weren't variants)
- ❌ No fallback strategy
- ❌ No way to see what went wrong

**After**:
- ✅ Skips overly broad matches
- ✅ Uses most specific patterns first
- ✅ Has direct search fallback
- ✅ Scrolls to ensure visibility
- ✅ Saves debug screenshots
- ✅ Checks up to 10 containers

## Alternative Debugging

If it still doesn't work, the debug screenshot will show:
- Where the size selector is on the page
- What the HTML structure looks like
- Whether there's something blocking it

Then we can add the exact selector needed for Allbirds.
