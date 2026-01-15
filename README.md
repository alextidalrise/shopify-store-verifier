# Shopify Store Verifier

A robust web scraper for verifying Shopify stores at scale. This tool can:

1. **Verify Multi-Currency Support**: Detect if stores support multiple currencies and allow checkout in local currencies
2. **Detect Post-Purchase Upsells**: Identify if stores are running post-purchase upsell flows

Built with Playwright for reliable browser automation that works across different Shopify themes and customizations.

## Features

- ✅ **Browser Automation**: Uses Playwright to handle JavaScript-heavy Shopify stores
- ✅ **Theme-Agnostic**: Works across different Shopify themes by using multiple selector patterns
- ✅ **Batch Processing**: Process thousands of stores with progress tracking and checkpointing
- ✅ **Concurrent Execution**: Run multiple verifications in parallel for speed
- ✅ **Comprehensive Results**: Exports results to CSV and JSON formats
- ✅ **Error Handling**: Robust error handling with detailed error messages
- ✅ **Progress Tracking**: Real-time progress updates and checkpoint saves

## Installation

### Prerequisites

- Python 3.10 or higher
- pip

### Setup

1. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

2. **Install Playwright browsers:**

```bash
playwright install chromium
```

That's it! You're ready to go.

## Usage

### Single Store Verification

To verify a single store:

```python
import asyncio
from shopify_verifier import ShopifyVerifier

async def main():
    verifier = ShopifyVerifier(headless=True)
    result = await verifier.verify_store("https://your-store.myshopify.com")
    
    print(f"Multiple currencies: {result.multiple_currencies_supported}")
    print(f"Post-purchase upsells: {result.post_purchase_upsell_detected}")
    print(f"Detected currencies: {result.detected_currencies}")

asyncio.run(main())
```

Or run the provided example:

```bash
python shopify_verifier.py
```

### Batch Verification (Thousands of Stores)

#### From a Text File

Create a text file with one store URL per line:

```
https://store1.com
https://store2.com
https://store3.com
```

Then run:

```bash
python batch_verifier.py
```

Or use the API:

```python
import asyncio
from batch_verifier import BatchVerifier

async def main():
    batch = BatchVerifier(
        output_dir="results",
        max_concurrent=5  # Number of parallel verifications
    )
    await batch.run("stores.txt", input_format="txt")

asyncio.run(main())
```

#### From a CSV File

If you have a CSV file with store URLs:

```csv
store_name,url,category
Store 1,https://store1.com,Fashion
Store 2,https://store2.com,Electronics
```

```python
import asyncio
from batch_verifier import BatchVerifier

async def main():
    batch = BatchVerifier(output_dir="results", max_concurrent=5)
    await batch.run(
        "stores.csv",
        input_format="csv",
        url_column="url"  # Name of the column with URLs
    )

asyncio.run(main())
```

## Configuration

### ShopifyVerifier Options

```python
verifier = ShopifyVerifier(
    headless=True,  # Run browser in headless mode (no GUI)
    timeout=30000   # Timeout in milliseconds (30 seconds)
)
```

### BatchVerifier Options

```python
batch = BatchVerifier(
    output_dir="results",  # Directory to save results
    max_concurrent=5       # Number of concurrent verifications
)
```

**Recommended max_concurrent values:**
- **3-5** for stability and avoiding rate limits
- **10+** if you have good bandwidth and want speed (may cause issues with some stores)

## Output

### Results Files

All results are saved to the `results/` directory (or your specified output directory):

1. **CSV File** (`results_TIMESTAMP.csv`): Tabular format for easy analysis in Excel/Google Sheets
2. **JSON File** (`results_TIMESTAMP.json`): Detailed results with full data structures
3. **Summary** (`summary_TIMESTAMP.json`): Overall statistics and metrics

### Checkpoint Files

When processing large batches, checkpoint files are saved every 50 stores:
- `checkpoint_50_of_1000.json`
- `checkpoint_100_of_1000.json`
- etc.

This allows you to resume if the process is interrupted.

### Result Fields

Each verification result contains:

| Field | Description |
|-------|-------------|
| `store_url` | The store URL that was verified |
| `success` | Whether verification completed successfully |
| `error_message` | Error details if verification failed |
| `multiple_currencies_supported` | Boolean: Store supports multiple currencies |
| `currency_selector_found` | Boolean: Currency selector UI element found |
| `detected_currencies` | List of currency codes found (e.g., ["USD", "GBP", "EUR"]) |
| `homepage_currency` | Currency detected on homepage |
| `checkout_currency` | Currency detected in checkout |
| `post_purchase_upsell_detected` | Boolean: Post-purchase upsell detected |
| `post_purchase_details` | Details about detected upsell indicators |
| `product_url` | URL of product used for testing |
| `reached_checkout` | Boolean: Successfully reached checkout page |

## How It Works

### Currency Verification

1. **Homepage Analysis**: Visits the store homepage and looks for currency selector UI elements
2. **Product Discovery**: Finds a product using multiple strategies (collections, homepage, API)
3. **Add to Cart**: Adds product to cart using various selector patterns
4. **Checkout Navigation**: Navigates to checkout page
5. **Currency Detection**: Detects currency from JavaScript objects, meta tags, and page content

### Post-Purchase Upsell Detection

Detects post-purchase upsells by looking for:
- Common post-purchase app identifiers in page source
- Shopify Scripts API usage
- Known post-purchase app domains (ReConvert, Zipify, CartHook, AfterSell, etc.)

**Note**: This is detection-based rather than requiring actual purchase completion, making it practical for bulk scanning.

## Performance

- **Single store**: ~15-30 seconds per store (depending on store speed)
- **Batch with max_concurrent=5**: Can process ~600 stores per hour
- **Memory usage**: ~200-400MB per concurrent browser instance

## Troubleshooting

### Common Issues

**Issue**: `playwright._impl._api_types.Error: Executable doesn't exist`
**Solution**: Run `playwright install chromium`

**Issue**: Timeouts on slow stores
**Solution**: Increase timeout: `ShopifyVerifier(timeout=60000)`

**Issue**: Too many failures
**Solution**: 
- Reduce `max_concurrent` to 3 or less
- Check your internet connection
- Some stores may have bot protection (expected)

**Issue**: Browser crashes
**Solution**: Reduce `max_concurrent` to prevent memory issues

### Debug Mode

To see the browser in action (helpful for debugging):

```python
verifier = ShopifyVerifier(headless=False)
```

This will show the browser window so you can see what's happening.

## Limitations

1. **Post-purchase detection is indicator-based**: We detect signs of post-purchase apps but don't complete actual purchases (which would require payment info)
2. **Some stores have bot protection**: May block automated access (expected for some stores)
3. **Theme variations**: While we handle many themes, some custom implementations may not be detected
4. **Rate limiting**: Verifying too many stores from the same IP may trigger rate limits

## Example Output

```
===========================================================
VERIFICATION SUMMARY
===========================================================
Total stores: 1000
Successful verifications: 847
Failed verifications: 153
Success rate: 84.7%

Currency Support:
  - Stores with multiple currencies: 234 (23.4%)
  - Stores with currency selector: 267

Post-Purchase Upsells:
  - Stores with upsells detected: 156 (15.6%)

Checkout Reached: 823 (82.3%)

Total duration: 3247.2 seconds (54.1 minutes)
Average time per store: 3.2 seconds
===========================================================
```

## Advanced Usage

### Custom Processing

```python
from shopify_verifier import ShopifyVerifier

async def process_stores_custom():
    verifier = ShopifyVerifier(headless=True)
    stores = ["store1.com", "store2.com", "store3.com"]
    
    for store in stores:
        result = await verifier.verify_store(store)
        
        # Custom processing
        if result.multiple_currencies_supported:
            print(f"{store} supports: {result.detected_currencies}")
        
        if result.post_purchase_upsell_detected:
            print(f"{store} has upsells: {result.post_purchase_details}")
```

### Filtering Results

```python
import json

# Load results
with open("results/results_20260115_143022.json") as f:
    results = json.load(f)

# Filter stores with both multi-currency and upsells
elite_stores = [
    r for r in results 
    if r['multiple_currencies_supported'] and r['post_purchase_upsell_detected']
]

print(f"Found {len(elite_stores)} stores with both features")
```

## License

MIT License - feel free to use and modify as needed.

## Contributing

This is a focused tool for Shopify verification. If you encounter stores that aren't detected properly, feel free to adjust the selector patterns in `shopify_verifier.py`.
