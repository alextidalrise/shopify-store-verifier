# Product Variant Handling

## The Problem

Many Shopify stores (like Allbirds) require you to **select a variant** (size, color, etc.) before the "Add to Cart" button appears or becomes enabled.

**Previous behavior:**
- Only handled dropdown `<select>` elements
- Didn't wait for button to become enabled
- Failed on stores with button-based size selectors

**Result:** "Could not add product to cart" errors

## The Solution

Enhanced variant selection with two strategies:

### Strategy 1: Dropdown Selectors (Traditional)
```html
<select name="Size">
  <option>Small</option>
  <option>Medium</option>
  <option>Large</option>
</select>
```

Handled by selecting the first available option from dropdown.

### Strategy 2: Button/Swatch Selectors (Modern)
```html
<fieldset>
  <input type="radio" name="Size" value="8">
  <input type="radio" name="Size" value="9">
  <input type="radio" name="Size" value="10">
</fieldset>
```

Or button-based:
```html
<button data-variant="123" class="size-button">Size 8</button>
<button data-variant="124" class="size-button">Size 9</button>
<button data-variant="125" class="size-button">Size 10</button>
```

## Detection Patterns

The code now checks for variants using these patterns:

### Button/Radio Patterns
- `button[data-variant]` - Direct variant buttons
- `button[data-option-value]` - Option value buttons
- `input[type="radio"][name*="option"]` - Radio inputs for options
- `input[type="radio"][name*="Size"]` - Size-specific radios
- `input[type="radio"][name*="Color"]` - Color-specific radios
- `[class*="variant-button"]` - Variant button classes
- `[class*="size-button"]` - Size button classes
- `[class*="swatch"]` - Color/pattern swatches
- `[class*="ProductOption"]` - Product option classes
- `fieldset input[type="radio"]` - Fieldset-based options
- `fieldset button` - Fieldset buttons
- `label[for*="option"]` - Option labels (for hidden radios)
- `label[for*="variant"]` - Variant labels

## Selection Logic

### 1. Find Variants
```
Checking for product variants (size, color, etc.)...
  Found 7 button/swatch variant(s) with pattern: fieldset input[type="radio"]
```

### 2. Select First Available
```
  Selecting variant: 8
  ✓ Variant selected successfully
```

**Smart selection:**
- Skips sold-out variants (checks for `sold-out`, `disabled` classes)
- Skips disabled elements (`aria-disabled="true"`, `disabled` attribute)
- Tries first 10 options to find an available one
- Shows variant name/value when possible

### 3. Wait for Add-to-Cart
```
Looking for add to cart button...
  ✓ Found enabled add to cart button (pattern 1/8)
    Pattern: button[name="add"]
    Button text: Add to Cart
  ✓ Successfully clicked add to cart button
```

**Key improvements:**
- Waits 1 second after variant selection (for JS to update DOM)
- Checks if button is **enabled** (not just visible)
- Waits up to 2 seconds for button to become enabled
- Shows button text for confirmation

## Console Output

### Before (Dropdown Only)
```
Adding product to cart...
  Failed to find add to cart button after trying 8 patterns
✗ FAILED: Could not add product to cart
```

### After (Button-Based Variants)
```
Adding product to cart...
  Checking for product variants (size, color, etc.)...
  Found 7 button/swatch variant(s) with pattern: fieldset input[type="radio"]
    Selecting variant: 8
    ✓ Variant selected successfully
  Looking for add to cart button...
  ✓ Found enabled add to cart button (pattern 1/8)
    Pattern: button[name="add"]
    Button text: Add to Cart
  ✓ Successfully clicked add to cart button
```

## Store Examples

### Allbirds
**Variant type:** Radio buttons in fieldset
**Pattern matched:** `fieldset input[type="radio"]`
**Result:** ✓ Size selected, add to cart enabled

### Traditional Stores
**Variant type:** Dropdown `<select>`
**Pattern matched:** `select[name*="option"]`
**Result:** ✓ Option selected from dropdown

### No Variants
**Variant type:** None (simple product)
**Pattern matched:** None
**Output:** "No variants detected (product may not require variant selection)"
**Result:** ✓ Proceeds to add to cart

## Why This Works

1. **Multiple strategies**: Handles both old and new themes
2. **Smart detection**: Checks 14+ patterns for variant selectors
3. **Availability checking**: Skips sold-out options
4. **Timing**: Waits for DOM updates after selection
5. **Enabled check**: Ensures button is clickable before attempting

## Testing

Test with stores that have variants:

```python
# test_single_store.py
test_store = "https://www.allbirds.com"  # Button-based variants
# or
test_store = "https://www.bombas.com"    # Various variants
```

Expected output:
```
Checking for product variants...
  Found X button/swatch variant(s)...
  Selecting variant: [name]
  ✓ Variant selected successfully
Looking for add to cart button...
  ✓ Found enabled add to cart button
  ✓ Successfully clicked add to cart button
```

## Edge Cases

### Sold Out Variants
```
Found 5 button/swatch variant(s)...
  Selecting variant: Small
  (skipped - sold out)
  Selecting variant: Medium
  ✓ Variant selected successfully
```

### All Sold Out
```
Found variants but none were selectable
```
Falls back to trying add-to-cart anyway (some stores allow it).

### No Variants Required
```
No variants detected (product may not require variant selection)
```
Proceeds normally to add-to-cart.

## Future Enhancements

Potential improvements:
- Select specific variant (e.g., always choose "Medium")
- Handle quantity selectors
- Handle multi-step variant selection (size, then color)
- Handle variant picker modals/pop-ups
- Detect if product is out of stock before attempting

## Files Changed

- `shopify_verifier.py`:
  - New method: `_select_variant()` - Handles variant selection
  - Enhanced: `_find_and_click_add_to_cart()` - Calls variant selection first
  - Added: 14+ variant selector patterns
  - Added: Enabled button checking with timeout
  - Enhanced: Logging for better debugging

---

**Bottom line:** The verifier now handles modern button-based variant selectors (like Allbirds) in addition to traditional dropdowns, significantly improving success rates on real-world stores.
