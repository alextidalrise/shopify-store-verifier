# Getting Started with Shopify Store Verifier

This guide will walk you through setting up and using the Shopify Store Verifier in just a few minutes.

## Quick Start (5 minutes)

### Step 1: Install Dependencies

**On Mac/Linux:**
```bash
./setup.sh
```

**On Windows:**
```bash
setup.bat
```

Or manually:
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 2: Test with Sample Stores

Run the quick start script to verify everything works:

```bash
python quick_start.py
```

This will test 3 sample Shopify stores and show you the browser automation in action.

**Expected output:**
- Browser window opens (unless headless mode is enabled)
- Script navigates to each store
- Adds products to cart
- Goes to checkout
- Detects currencies and post-purchase upsells
- Prints results

**Time:** ~2-3 minutes for 3 stores

### Step 3: Process Your Own Stores

#### Option A: Small batch (< 100 stores)

1. Create a text file with your store URLs:

```bash
# Create stores.txt with one URL per line
cat > stores.txt << EOF
https://store1.com
https://store2.com
https://store3.com
EOF
```

2. Edit `batch_verifier.py` and update the main function:

```python
async def main():
    batch = BatchVerifier(output_dir="results", max_concurrent=3)
    await batch.run("stores.txt", input_format="txt")

asyncio.run(main())
```

3. Run it:

```bash
python batch_verifier.py
```

#### Option B: Large batch (1000+ stores)

For better performance with thousands of stores:

1. Create your input file (text or CSV)

2. Adjust concurrency based on your system:

```python
# For most systems, 3-5 concurrent is stable
batch = BatchVerifier(output_dir="results", max_concurrent=5)

# For powerful systems with good internet, you can go higher
batch = BatchVerifier(output_dir="results", max_concurrent=10)
```

3. Run it:

```bash
python batch_verifier.py
```

**Performance estimates:**
- 3 concurrent: ~300-400 stores/hour
- 5 concurrent: ~500-600 stores/hour
- 10 concurrent: ~800-1000 stores/hour (may be unstable)

## Understanding the Results

### Output Files

After running batch verification, check the `results/` directory:

```
results/
├── results_20260115_143022.csv      # Spreadsheet format
├── results_20260115_143022.json     # Detailed format
├── summary_20260115_143022.json     # Summary statistics
└── checkpoint_*.json                # Progress checkpoints
```

### CSV Fields

Open the CSV file in Excel or Google Sheets:

| Column | What it means |
|--------|---------------|
| `store_url` | The store you tested |
| `success` | TRUE if verification completed |
| `multiple_currencies_supported` | TRUE if store has multiple currencies |
| `detected_currencies` | List like "USD, GBP, EUR" |
| `post_purchase_upsell_detected` | TRUE if post-purchase upsells found |
| `reached_checkout` | TRUE if bot reached checkout page |

### Quick Analysis

Use the analysis tool:

```bash
python analyze_results.py results/results_20260115_143022.json
```

This shows:
- Overall success rate
- How many stores have multi-currency
- How many stores have post-purchase upsells
- Common errors
- Currency distribution

## Common Scenarios

### Scenario 1: "I want stores with both multi-currency AND upsells"

```bash
# 1. Run verification
python batch_verifier.py

# 2. Analyze results
python analyze_results.py results/results_TIMESTAMP.json

# 3. Check results/elite_stores.csv for stores with both features
```

### Scenario 2: "I have a CSV with store data"

Your CSV:
```csv
brand_name,website,category
Cool Brand,https://coolbrand.com,Fashion
Tech Store,https://techstore.com,Electronics
```

Python code:
```python
from batch_verifier import BatchVerifier
import asyncio

async def main():
    batch = BatchVerifier(output_dir="results", max_concurrent=5)
    await batch.run(
        "my_stores.csv",
        input_format="csv",
        url_column="website"  # The column name with URLs
    )

asyncio.run(main())
```

### Scenario 3: "I want to process 5000+ stores"

1. Split your stores into chunks of 1000-2000
2. Run batch verifier on each chunk
3. Combine results:

```python
import json
from pathlib import Path

# Load all result files
all_results = []
for file in Path("results").glob("results_*.json"):
    with open(file) as f:
        all_results.extend(json.load(f))

# Save combined results
with open("results/combined_results.json", "w") as f:
    json.dump(all_results, f, indent=2)
```

### Scenario 4: "Some verifications are failing"

Common causes and solutions:

**Issue: "Could not find any product page"**
- Store might not have products listed
- Store might be password-protected
- This is expected for some stores

**Issue: "Timeout"**
- Store is very slow
- Increase timeout: `ShopifyVerifier(timeout=60000)`  # 60 seconds

**Issue: "Could not add product to cart"**
- Product might be out of stock
- Store might have custom add-to-cart implementation
- Expected for some stores with unusual themes

**Issue: Too many failures (>30%)**
- Reduce `max_concurrent` to 3 or less
- Check your internet connection
- Increase timeout values

## Pro Tips

### 1. Headless Mode for Speed

For production runs, always use headless mode:

```python
verifier = ShopifyVerifier(headless=True)  # No GUI = faster
```

### 2. Test First

Before running thousands of stores:
```python
# Test with 10 stores first
test_stores = all_stores[:10]
```

### 3. Monitor Progress

The batch verifier shows real-time progress:
```
[1/1000] Verifying: https://store1.com
[1/1000] https://store1.com - ✓ SUCCESS
[2/1000] Verifying: https://store2.com
...
```

Watch for patterns in failures to identify systematic issues.

### 4. Resume from Checkpoint

If the process crashes, you can resume:

```python
import json

# Load checkpoint
with open("results/checkpoint_500_of_1000.json") as f:
    completed = json.load(f)

completed_urls = {r['store_url'] for r in completed}

# Filter remaining stores
remaining_stores = [s for s in all_stores if s not in completed_urls]

# Continue with remaining stores
```

### 5. Custom Filtering

Filter results programmatically:

```python
import json

with open("results/results_20260115_143022.json") as f:
    results = json.load(f)

# Stores with USD and EUR
multi_currency = [
    r for r in results 
    if 'USD' in r['detected_currencies'] 
    and 'EUR' in r['detected_currencies']
]

print(f"Found {len(multi_currency)} stores with USD and EUR")
```

## Troubleshooting

### "playwright._impl._api_types.Error: Executable doesn't exist"

**Solution:** Install Playwright browsers:
```bash
playwright install chromium
```

### "Too many browser crashes"

**Solution:** Reduce concurrent verifications:
```python
batch = BatchVerifier(max_concurrent=2)  # Lower = more stable
```

### "Very slow performance"

**Causes:**
- Stores with slow loading times (expected)
- Too many concurrent verifications
- Slow internet connection

**Solutions:**
- Increase `max_concurrent` for faster processing (if stable)
- Use a faster internet connection
- Run on a more powerful machine

### "Results seem inaccurate"

**Currency detection:**
- We detect currency selectors and checkout currency
- Some stores might show USD by default but support other currencies
- This is a limitation of automated detection

**Post-purchase upsells:**
- We detect *indicators* of post-purchase apps
- We don't complete actual purchases (can't without payment info)
- False positives are possible but rare

## Next Steps

1. **Read the full README:** `cat README.md` or open README.md
2. **Try the quick start:** `python quick_start.py`
3. **Process your stores:** Edit `batch_verifier.py` with your store list
4. **Analyze results:** `python analyze_results.py results/your_results.json`

## Support

For issues or questions:
1. Check the README.md for detailed documentation
2. Review the code comments in `shopify_verifier.py`
3. Test with `headless=False` to see what the browser is doing

## Example Complete Workflow

```bash
# 1. Setup (one time)
./setup.sh

# 2. Create your store list
cat > my_stores.txt << EOF
https://store1.com
https://store2.com
https://store3.com
EOF

# 3. Run verification
python batch_verifier.py

# 4. Analyze results
python analyze_results.py results/results_*.json

# 5. Open results in Excel
# Open results/results_TIMESTAMP.csv in Excel or Google Sheets

# 6. Find elite stores (multi-currency + upsells)
# Check results/elite_stores.csv
```

That's it! You're ready to verify thousands of Shopify stores. Happy analyzing!
