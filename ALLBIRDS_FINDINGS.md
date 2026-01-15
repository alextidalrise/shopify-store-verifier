# Allbirds Size Selection - Browser Testing Findings

## What I Discovered

### 1. Geolocation Popup (CRITICAL)
**The Issue**: A "Where are we shipping to?" popup appears with country flags (US, ES/Spain)
- This popup **blocks all interaction** with the page
- **Solution that works**: Press `Escape` key to close it
- The popup appears on every page load

**Screenshot Evidence**: The popup shows two country flags (US and Spain) with the heading "Where are we shipping to?"

### 2. Size Selection Structure

Based on your screenshot and my testing, here's the Allbirds size selection structure:

```
Product Page Layout:
├── Color/Style tabs: "ALL", "CLASSIC", "LIMITED"
├── Size tabs: "MEN'S SIZES" ← Tab (might need clicking)
│              "WOMEN'S SIZES" ← Tab
└── Size buttons:
    ├── 8  ← Button (clickable)
    ├── 9  ← Button (clickable)
    ├── 10 ← Button (clickable)
    ├── 11 ← Button (gray = selected or emphasized)
    ├── 12 ← Button (clickable)
    ├── 13 ← Button (clickable)
    └── 14 ← Button (clickable)
```

**Key Findings**:
1. **Not dropdown selectors** - these are `<button>` or `<input type="radio">` elements
2. **Tab selection first**: May need to ensure "MEN'S SIZES" tab is selected
3. **Individual size buttons**: Each size (8, 9, 10, etc.) is a separate clickable element
4. **Visual feedback**: Selected size shows gray background

### 3. What Your Script Was Doing

From your description: "We clicked from women's to men's sizes, but then didn't end up selecting a size"

**Analysis**:
- ✅ Script successfully clicked the "MEN'S SIZES" tab
- ❌ Script did NOT click an individual size button (8, 9, 10, etc.)
- Result: Add-to-cart button stays disabled because no size is selected

## Why Our Code Needs Updating

### Current Variant Selection Patterns

Our code looks for these patterns:
```python
button_patterns = [
    'button[data-variant]',           # ← Allbirds might not use this
    'input[type="radio"][name*="option"]',  # ← Possible match
    'fieldset input[type="radio"]',    # ← Likely match
    # ... others
]
```

### The Problem

1. **Tab vs Button confusion**: The code might click the "MEN'S SIZES" tab and think it selected a variant
2. **Need to click actual size**: Must click on "8", "9", "10", etc. buttons
3. **Multiple click steps**: Tab selection + size button click

## Recommended Code Changes

### 1. Enhanced Geolocation Handling

```python
async def _close_geolocation_popup(self, page: Page) -> bool:
    """
    Specifically handle Allbirds-style geolocation popups.
    """
    try:
        # Try Escape key first (works for Allbirds)
        await page.keyboard.press('Escape')
        await page.wait_for_timeout(1000)
        print("  Pressed Escape to close geolocation popup")
        return True
    except:
        return False
```

### 2. Better Size Selection Logic

```python
async def _select_variant(self, page: Page) -> bool:
    # ... existing code ...
    
    # NEW: Strategy for button-based sizes with tabs
    try:
        # Step 1: Look for size/variant tabs (MEN'S SIZES, WOMEN'S SIZES, etc.)
        tab_patterns = [
            'button:has-text("MEN\'S SIZES")',
            'button:has-text("WOMEN\'S SIZES")',
            '[role="tab"]:has-text("MEN")',
            '[role="tab"]:has-text("WOMEN")',
        ]
        
        for tab_pattern in tab_patterns:
            try:
                tab = page.locator(tab_pattern).first
                if await tab.count() > 0 and await tab.is_visible(timeout=1000):
                    # Click the tab but DON'T return - we need to click a size too
                    await tab.click(timeout=2000)
                    await page.wait_for_timeout(500)
                    print(f"    Clicked size category tab")
                    break
            except:
                continue
        
        # Step 2: Now click an actual size button
        # Look for buttons with numbers (8, 9, 10, 11, etc.)
        size_patterns = [
            'button:has-text("8")',   # Try smallest size first
            'button:has-text("9")',
            'button:has-text("10")',
            'button:has-text("11")',
            # Could also try:
            # 'button[aria-label*="Size"]',
            # 'label:has-text("8")',  # For label-wrapped inputs
        ]
        
        for size_pattern in size_patterns:
            try:
                size_btn = page.locator(size_pattern).first
                if await size_btn.count() > 0 and await size_btn.is_visible(timeout=1000):
                    # Check if it's disabled/sold out
                    is_disabled = await size_btn.is_disabled()
                    if not is_disabled:
                        await size_btn.click(timeout=2000)
                        await page.wait_for_timeout(800)
                        print(f"    Selected size via button: {size_pattern}")
                        return True
            except:
                continue
                
    except Exception as e:
        print(f"    Tab-based size selection failed: {str(e)[:50]}")
```

### 3. Add-to-Cart Detection After Size Selection

```python
# After selecting variant, wait for add-to-cart to become enabled
await page.wait_for_timeout(1000)  # Already in code

# Could also add explicit wait:
try:
    # Wait up to 5 seconds for an enabled add-to-cart button
    await page.wait_for_selector('button[name="add"]:not([disabled])', timeout=5000)
    print("  Add-to-cart button is now enabled")
except:
    print("  Warning: Add-to-cart button may still be disabled")
```

## Testing Steps

### Manual Test with Browser

1. Navigate to: `https://www.allbirds.com/products/mens-wool-runners`
2. **Wait for geolocation popup** → Press `Escape`
3. **Scroll to size selection**
4. **Click "MEN'S SIZES" tab** (if needed)
5. **Click a size button** (e.g., "10")
6. **Observe**: Add-to-cart button should become enabled
7. **Click "Add to cart"**

### Automated Test

```bash
python test_single_store.py
# With Allbirds URL set in the file
```

**Expected console output**:
```
Checking for pop-ups on homepage...
  Pressed Escape to close geolocation popup
Finding a product...
  Found product: https://www.allbirds.com/products/mens-wool-runners
Adding product to cart...
  Checking for product variants (size, color, etc.)...
  Clicked size category tab
  Selected size via button: button:has-text("10")
  Looking for add to cart button...
  ✓ Found enabled add to cart button
  ✓ Successfully clicked add to cart button
```

## Summary

**The Flow That Works**:
1. Close geolocation popup (Escape key)
2. Navigate to product page
3. Click "MEN'S SIZES" tab (optional, depends on default)
4. Click individual size button ("8", "9", "10", etc.)
5. Wait for add-to-cart button to enable
6. Click add-to-cart

**Why Previous Attempts Failed**:
- Geolocation popup blocked interaction
- Code clicked tab but not individual size
- Didn't wait for button to enable after size selection

## Next Steps

1. Update `_select_variant()` with tab + button logic
2. Add specific Escape-key handler for geolocation
3. Test with `test_single_store.py`
4. Verify add-to-cart works after size selection
