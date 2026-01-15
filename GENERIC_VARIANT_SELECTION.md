# Generic Variant Selection - Design Philosophy

## The Problem with Specific Selectors

**Original approach** (too specific):
```python
# BAD: Only works for shoe sizes
'button:has-text("8")',
'button:has-text("9")',
'button:has-text("10")',
```

**Why it's bad**:
- Only works for numeric shoe sizes
- Breaks for clothing (S, M, L, XL)
- Breaks for colors (Red, Blue, Black)
- Breaks for materials (Cotton, Leather)
- Different languages have different text
- Not scalable

## The Solution: Container-Based Selection

### Core Philosophy

Instead of looking for specific values, we:
1. **Find containers** that hold variant options
2. **Find clickable elements** within those containers
3. **Click the first available** one (regardless of its value)

### How It Works

```
Store Page Structure:
├── Container 1 (e.g., Size)
│   ├── Option: Small
│   ├── Option: Medium ← Click first available
│   └── Option: Large
├── Container 2 (e.g., Color)
│   ├── Option: Red ← Click first available
│   ├── Option: Blue
│   └── Option: Black (sold out)
└── Container 3 (e.g., Material)
    └── ...
```

**We don't care what the values are** - we just find and click them!

## Implementation Details

### Step 1: Find Variant Containers

```python
container_patterns = [
    'fieldset',                          # Semantic HTML
    '[role="radiogroup"]',               # ARIA role
    'div[class*="variant"]',             # Class naming
    'div[class*="option"]',
    'div[class*="product-form__input"]',
    'div[data-product-option]',          # Data attributes
]
```

These patterns match **any container** regardless of what variant type it holds.

### Step 2: Find Options Within Containers

```python
option_selectors = [
    'input[type="radio"]',     # Radio buttons
    'button:not([disabled])',  # Enabled buttons  
    'label[for]',              # Labels (wrap hidden radios)
    '[role="radio"]',          # ARIA radio role
    'a[class*="swatch"]',      # Swatch links
]
```

These patterns match **any clickable option** regardless of its value.

### Step 3: Smart Selection Logic

```python
# For each option:
1. Check if visible
2. Check if disabled/sold-out
3. Check if already selected
4. If available → CLICK IT
5. Don't care what the value is!
```

## Real-World Examples

### Example 1: Allbirds (Shoe Sizes)

**Container**: `<fieldset>`
**Options**: `<button>8</button>`, `<button>9</button>`, etc.

**Our code**:
- Finds the fieldset ✓
- Finds button options ✓
- Clicks first available button ✓
- **Works without knowing they're shoe sizes!**

### Example 2: Clothing Store (Sizes)

**Container**: `<div class="product-form__input">`
**Options**: `<label>S</label>`, `<label>M</label>`, `<label>L</label>`

**Our code**:
- Finds the div container ✓
- Finds label options ✓
- Clicks first available label ✓
- **Works without knowing they're clothing sizes!**

### Example 3: Color Swatches

**Container**: `<div class="variant-selector">`
**Options**: `<a class="swatch">Red</a>`, `<a class="swatch">Blue</a>`

**Our code**:
- Finds the variant-selector div ✓
- Finds swatch links ✓
- Clicks first available swatch ✓
- **Works without knowing they're colors!**

### Example 4: Multi-Variant Products

**Container 1**: Size fieldset
**Container 2**: Color div

**Our code**:
- Processes each container separately ✓
- Selects one option from each ✓
- **Handles multiple variant types automatically!**

## Special Handling

### Tab-Style Containers (Allbirds Case)

Some stores have **tabs** that group variants:

```html
<div>
  <button>MEN'S SIZES</button>  ← Tab (needs activation)
  <button>WOMEN'S SIZES</button> ← Tab
  
  <div class="size-options">
    <button>8</button>  ← Actual size
    <button>9</button>  ← Actual size
  </div>
</div>
```

**Our approach**:
1. Detect if there's a tab/legend element
2. Click it to activate the group
3. Then select option within the group

```python
# Check for tabs/legends first
tab_patterns = [
    'fieldset legend',
    '[role="radiogroup"]',
    'div[class*="tab"]',
]

# Click tab if found (activates the group)
# Then proceed to select options within
```

### Sold Out / Disabled Options

**Detection patterns**:
```python
# Skip if:
- disabled_attr is not None        # disabled="true"
- aria_disabled == 'true'           # aria-disabled="true"
- 'sold-out' in classes             # class="sold-out"
- 'unavailable' in classes          # class="unavailable"  
- 'disabled' in classes             # class="disabled"
```

**Behavior**: Try next option automatically

### Already Selected Options

**Detection**:
```python
if aria_checked == 'true':  # aria-checked="true"
    print("Already selected")
    break  # Don't click again
```

**Behavior**: Move to next container

## Logging Output

### Before (Specific)
```
Found add to cart button
Failed - button disabled
```

### After (Generic + Verbose)
```
Found 2 variant container(s): fieldset
  Variant group: Size
    Found 7 options (button:not([disabled]))
      Selecting: 10
      ✓ Variant selected
  Variant group: Color  
    Found 5 options (a[class*="swatch"])
      Selecting: Natural White
      ✓ Variant selected
Looking for add to cart button...
  ✓ Found enabled add to cart button
```

**Benefits**:
- See which containers were found
- See which options were available
- See which options were selected
- Debug issues easily

## Advantages

### 1. Works Across Different Variant Types
- ✅ Sizes (8, 9, S, M, L, XL, One Size)
- ✅ Colors (Red, Blue, any color name)
- ✅ Materials (Cotton, Leather, Wood)
- ✅ Styles (Classic, Modern, Vintage)
- ✅ Lengths (Short, Regular, Long)
- ✅ Widths (Narrow, Regular, Wide)
- ✅ Any custom variant type!

### 2. Works Across Different Themes
- ✅ Different HTML structures
- ✅ Different CSS classes
- ✅ Different JavaScript frameworks
- ✅ Custom Shopify themes

### 3. Works Across Languages
- ✅ English, Spanish, French, etc.
- ✅ Doesn't depend on text content
- ✅ Uses structural patterns instead

### 4. Handles Multiple Variants
- ✅ Products with Size + Color
- ✅ Products with Size + Color + Material
- ✅ Any combination of variant types

### 5. Robust to Changes
- ✅ Store updates theme → still works
- ✅ New variant types added → still works
- ✅ Different stores → still works

## Testing Strategy

### Unit Test Approach

Test with products that have:
1. ✅ Only size variants
2. ✅ Only color variants
3. ✅ Size + color variants
4. ✅ Three or more variant types
5. ✅ Tab-style variant groups
6. ✅ Some sold-out options
7. ✅ Different languages/regions

### Expected Behavior

**Should succeed**:
- Any product with selectable variants
- Any variant type (size, color, material, etc.)
- Any theme/store implementation

**Should gracefully fail**:
- All options sold out → reports "none selectable"
- No variants required → reports "no variants detected"
- Password-protected products → handled upstream

## Comparison

### Old Approach
```python
# Try specific size buttons
'button:has-text("8")'   # Only works for size 8
'button:has-text("S")'   # Only works for Small
'button:has-text("Red")' # Only works for Red
# Need 100s of patterns for all possible values!
```

### New Approach
```python
# Find any container
container = find('fieldset')

# Find any clickable option inside
options = container.find('button:not([disabled])')

# Click first available
options[0].click()

# Works for ANY value!
```

## Future Enhancements

Potential improvements:
1. **Smart variant selection**: Prefer certain options (e.g., "Medium" over "Small")
2. **User preferences**: Let user specify preferred size/color
3. **Variant memory**: Remember successful patterns per store
4. **Multi-language support**: Better label detection
5. **Custom variant logic**: Store-specific overrides

## Summary

**Before**: Hardcoded specific values (sizes, colors)
**After**: Generic container-based selection

**Key insight**: We don't need to know what the variants ARE - we just need to find and click them!

**Result**: Works for:
- ✅ Any variant type
- ✅ Any store theme  
- ✅ Any language
- ✅ Any HTML structure
- ✅ Multiple variants
- ✅ Future variant types

**Philosophy**: **Structure over Content** - detect by HTML structure, not by text content.
