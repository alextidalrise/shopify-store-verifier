"""
Batch Verifier for processing thousands of Shopify stores.
Includes CSV import/export, progress tracking, and error handling.
"""

import asyncio
import csv
import json
from pathlib import Path
from datetime import datetime
from typing import List

from shopify_verifier import ShopifyVerifier, VerificationResult


class BatchVerifier:
    """Processes multiple stores with progress tracking and persistence."""
    
    def __init__(self, output_dir: str = "results", max_concurrent: int = 5):
        """
        Initialize batch verifier.
        
        Args:
            output_dir: Directory to save results
            max_concurrent: Maximum concurrent verifications
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.max_concurrent = max_concurrent
        self.verifier = ShopifyVerifier(headless=True)
        
    def load_stores_from_csv(self, filepath: str, url_column: str = "url") -> List[str]:
        """
        Load store URLs from a CSV file.
        
        Args:
            filepath: Path to CSV file
            url_column: Name of column containing URLs
            
        Returns:
            List of store URLs
        """
        stores = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get(url_column)
                if url:
                    stores.append(url.strip())
        return stores
    
    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL from various input formats.
        
        Handles:
        - Missing protocol (adds https://)
        - Trailing slashes and asterisks (removes)
        - http:// -> https://
        - Semicolon-separated URLs (takes first)
        - Whitespace
        
        Args:
            url: Raw URL string
            
        Returns:
            Normalized URL or None if empty
        """
        # Strip whitespace
        url = url.strip()
        
        # Skip empty lines
        if not url:
            return None
        
        # Handle semicolon-separated URLs (take the first one)
        if ';' in url:
            url = url.split(';')[0].strip()
        
        # Remove trailing /* or * or /
        url = url.rstrip('/*').rstrip('/')
        
        # Add https:// if no protocol
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Convert http to https
        if url.startswith('http://'):
            url = url.replace('http://', 'https://')
        
        return url
    
    def load_stores_from_txt(self, filepath: str) -> List[str]:
        """
        Load store URLs from a text file (one per line).
        Automatically normalizes URLs to handle various formats.
        
        Args:
            filepath: Path to text file
            
        Returns:
            List of normalized store URLs
        """
        stores = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                normalized = self.normalize_url(line)
                if normalized:
                    stores.append(normalized)
        return stores
    
    def save_results_to_csv(self, results: List[VerificationResult], filename: str = None):
        """
        Save results to a CSV file.
        
        Args:
            results: List of verification results
            filename: Output filename (auto-generated if None)
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"verification_results_{timestamp}.csv"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'store_url',
                'success',
                'error_message',
                'multiple_currencies_supported',
                'available_countries',
                'country_currency_pairs',
                'currency_switch_tested',
                'currency_switch_successful',
                'initial_currency',
                'switched_currency',
                'post_purchase_upsell_detected',
                'post_purchase_app_name',
                'post_purchase_requests',
                'product_url',
                'reached_checkout',
            ])
            writer.writeheader()
            
            for result in results:
                row = result.to_dict()
                # Convert lists/dicts to strings for CSV
                row['available_countries'] = ', '.join(row['available_countries']) if row['available_countries'] else ''
                row['country_currency_pairs'] = json.dumps(row['country_currency_pairs']) if row['country_currency_pairs'] else '{}'
                row['post_purchase_requests'] = str(len(row['post_purchase_requests'])) + ' requests' if row['post_purchase_requests'] else '0 requests'
                writer.writerow(row)
        
        print(f"\nResults saved to: {filepath}")
        return filepath
    
    def save_results_to_json(self, results: List[VerificationResult], filename: str = None):
        """
        Save results to a JSON file.
        
        Args:
            results: List of verification results
            filename: Output filename (auto-generated if None)
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"verification_results_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
        
        print(f"Results saved to: {filepath}")
        return filepath
    
    async def verify_stores_with_progress(
        self, 
        store_urls: List[str],
        checkpoint_interval: int = 50
    ) -> List[VerificationResult]:
        """
        Verify stores with progress tracking and checkpointing.
        
        Args:
            store_urls: List of store URLs
            checkpoint_interval: Save checkpoint every N stores
            
        Returns:
            List of verification results
        """
        results = []
        total = len(store_urls)
        
        print(f"\n{'='*60}")
        print(f"Starting batch verification of {total} stores")
        print(f"Max concurrent: {self.max_concurrent}")
        print(f"{'='*60}\n")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def verify_with_progress(index: int, url: str) -> VerificationResult:
            async with semaphore:
                print(f"[{index+1}/{total}] Verifying: {url}")
                try:
                    result = await self.verifier.verify_store(url)
                    status = "✓ SUCCESS" if result.success else f"✗ FAILED: {result.error_message}"
                    print(f"[{index+1}/{total}] {url} - {status}")
                    return result
                except Exception as e:
                    print(f"[{index+1}/{total}] {url} - ✗ EXCEPTION: {str(e)}")
                    return VerificationResult(
                        store_url=url,
                        success=False,
                        error_message=f"Exception: {str(e)}"
                    )
        
        # Process in batches for checkpointing
        for batch_start in range(0, total, checkpoint_interval):
            batch_end = min(batch_start + checkpoint_interval, total)
            batch_urls = store_urls[batch_start:batch_end]
            
            print(f"\n--- Processing batch {batch_start+1} to {batch_end} ---\n")
            
            tasks = [verify_with_progress(batch_start + i, url) for i, url in enumerate(batch_urls)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            for i, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    results.append(VerificationResult(
                        store_url=batch_urls[i],
                        success=False,
                        error_message=f"Task exception: {str(result)}"
                    ))
                else:
                    results.append(result)
            
            # Checkpoint save
            if batch_end < total:
                checkpoint_file = f"checkpoint_{batch_end}_of_{total}.json"
                self.save_results_to_json(results, checkpoint_file)
                print(f"\n✓ Checkpoint saved: {checkpoint_file}\n")
        
        return results
    
    def generate_summary(self, results: List[VerificationResult]) -> dict:
        """
        Generate a summary of verification results.
        
        Args:
            results: List of verification results
            
        Returns:
            Summary statistics dictionary
        """
        total = len(results)
        successful = sum(1 for r in results if r.success)
        failed = total - successful
        
        multiple_currencies = sum(1 for r in results if r.multiple_currencies_supported)
        currency_switch_tested = sum(1 for r in results if r.currency_switch_tested)
        post_purchase = sum(1 for r in results if r.post_purchase_upsell_detected)
        reached_checkout = sum(1 for r in results if r.reached_checkout)
        
        summary = {
            "total_stores": total,
            "successful_verifications": successful,
            "failed_verifications": failed,
            "success_rate": f"{(successful/total*100):.1f}%" if total > 0 else "0%",
            "multiple_currencies_count": multiple_currencies,
            "multiple_currencies_percentage": f"{(multiple_currencies/total*100):.1f}%" if total > 0 else "0%",
            "currency_switch_tested_count": currency_switch_tested,
            "post_purchase_upsell_count": post_purchase,
            "post_purchase_upsell_percentage": f"{(post_purchase/total*100):.1f}%" if total > 0 else "0%",
            "reached_checkout_count": reached_checkout,
            "reached_checkout_percentage": f"{(reached_checkout/total*100):.1f}%" if total > 0 else "0%",
        }
        
        return summary
    
    async def run(self, input_file: str, input_format: str = "csv", url_column: str = "url"):
        """
        Main entry point for batch verification.
        
        Args:
            input_file: Path to input file containing store URLs
            input_format: Format of input file ('csv' or 'txt')
            url_column: Column name for URLs (if CSV)
        """
        # Load stores
        if input_format == "csv":
            stores = self.load_stores_from_csv(input_file, url_column)
        elif input_format == "txt":
            stores = self.load_stores_from_txt(input_file)
        else:
            raise ValueError(f"Unsupported input format: {input_format}")
        
        if not stores:
            print("No stores found in input file!")
            return
        
        print(f"Loaded {len(stores)} stores from {input_file}")
        
        # Verify stores
        start_time = datetime.now()
        results = await self.verify_stores_with_progress(stores)
        end_time = datetime.now()
        
        duration = (end_time - start_time).total_seconds()
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.save_results_to_csv(results, f"results_{timestamp}.csv")
        self.save_results_to_json(results, f"results_{timestamp}.json")
        
        # Generate and display summary
        summary = self.generate_summary(results)
        
        print(f"\n{'='*60}")
        print("VERIFICATION SUMMARY")
        print(f"{'='*60}")
        print(f"Total stores: {summary['total_stores']}")
        print(f"Successful verifications: {summary['successful_verifications']}")
        print(f"Failed verifications: {summary['failed_verifications']}")
        print(f"Success rate: {summary['success_rate']}")
        print(f"\nCurrency Support:")
        print(f"  - Stores with multiple currencies: {summary['multiple_currencies_count']} ({summary['multiple_currencies_percentage']})")
        print(f"  - Stores with currency switch tested: {summary['currency_switch_tested_count']}")
        print(f"\nPost-Purchase Upsells:")
        print(f"  - Stores with upsells detected: {summary['post_purchase_upsell_count']} ({summary['post_purchase_upsell_percentage']})")
        print(f"\nCheckout Reached: {summary['reached_checkout_count']} ({summary['reached_checkout_percentage']})")
        print(f"\nTotal duration: {duration:.1f} seconds ({duration/60:.1f} minutes)")
        print(f"Average time per store: {duration/len(stores):.1f} seconds")
        print(f"{'='*60}\n")
        
        # Save summary
        summary['duration_seconds'] = duration
        summary['start_time'] = start_time.isoformat()
        summary['end_time'] = end_time.isoformat()
        
        with open(self.output_dir / f"summary_{timestamp}.json", 'w') as f:
            json.dump(summary, f, indent=2)


async def main():
    """Batch verification runner."""
    
    # ============================================
    # CONFIGURATION - EDIT THESE SETTINGS
    # ============================================
    
    # Your store list file (TXT or CSV)
    input_file = "my_stores.txt"
    
    # File format: "txt" or "csv"
    file_format = "txt"
    
    # If CSV, which column has URLs? (only needed if format="csv")
    csv_url_column = "url"
    
    # How many stores to process at once (3-5 recommended)
    concurrent = 5  # Back to parallel mode - domain redirect issues fixed!
    
    # Where to save results
    output_folder = "results"
    
    # ============================================
    
    print(f"Starting batch verification...")
    print(f"Input file: {input_file}")
    print(f"Concurrent: {concurrent}")
    print(f"Output: {output_folder}/")
    print("="*70 + "\n")
    
    # Run batch verification
    batch = BatchVerifier(output_dir=output_folder, max_concurrent=concurrent)
    
    if file_format == "csv":
        await batch.run(input_file, input_format="csv", url_column=csv_url_column)
    else:
        await batch.run(input_file, input_format="txt")


if __name__ == "__main__":
    asyncio.run(main())
