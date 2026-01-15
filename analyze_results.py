"""
Results Analysis Tool

Analyze and filter verification results.
"""

import json
import csv
from pathlib import Path
from typing import List, Dict
from collections import Counter


class ResultsAnalyzer:
    """Analyze verification results."""
    
    def __init__(self, results_file: str):
        """
        Initialize analyzer with a results file.
        
        Args:
            results_file: Path to JSON results file
        """
        self.results_file = results_file
        with open(results_file, 'r') as f:
            self.results = json.load(f)
    
    def get_summary(self) -> Dict:
        """Get overall summary statistics."""
        total = len(self.results)
        successful = sum(1 for r in self.results if r['success'])
        
        return {
            'total_stores': total,
            'successful': successful,
            'failed': total - successful,
            'success_rate': f"{(successful/total*100):.1f}%" if total > 0 else "0%",
            'multi_currency': sum(1 for r in self.results if r['multiple_currencies_supported']),
            'post_purchase_upsells': sum(1 for r in self.results if r['post_purchase_upsell_detected']),
            'reached_checkout': sum(1 for r in self.results if r['reached_checkout']),
        }
    
    def filter_by_criteria(self, **criteria) -> List[Dict]:
        """
        Filter results by criteria.
        
        Examples:
            filter_by_criteria(multiple_currencies_supported=True)
            filter_by_criteria(post_purchase_upsell_detected=True, success=True)
        """
        filtered = self.results
        for key, value in criteria.items():
            filtered = [r for r in filtered if r.get(key) == value]
        return filtered
    
    def get_currency_distribution(self) -> Dict[str, int]:
        """Get distribution of detected currencies."""
        all_currencies = []
        for result in self.results:
            # Get currencies from country_currency_pairs dict
            pairs = result.get('country_currency_pairs', {})
            if pairs:
                all_currencies.extend(pairs.values())
        return dict(Counter(all_currencies))
    
    def get_error_distribution(self) -> Dict[str, int]:
        """Get distribution of error messages."""
        errors = [r['error_message'] for r in self.results if not r['success'] and r['error_message']]
        return dict(Counter(errors))
    
    def export_filtered(self, filtered_results: List[Dict], output_file: str):
        """Export filtered results to a new file."""
        if output_file.endswith('.json'):
            with open(output_file, 'w') as f:
                json.dump(filtered_results, f, indent=2)
        elif output_file.endswith('.csv'):
            if filtered_results:
                with open(output_file, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=filtered_results[0].keys())
                    writer.writeheader()
                    for row in filtered_results:
                        # Convert lists/dicts to strings for CSV
                        csv_row = row.copy()
                        if isinstance(csv_row.get('available_countries'), list):
                            csv_row['available_countries'] = ', '.join(csv_row['available_countries'])
                        if isinstance(csv_row.get('country_currency_pairs'), dict):
                            csv_row['country_currency_pairs'] = json.dumps(csv_row['country_currency_pairs'])
                        if isinstance(csv_row.get('post_purchase_requests'), list):
                            csv_row['post_purchase_requests'] = f"{len(csv_row['post_purchase_requests'])} requests"
                        writer.writerow(csv_row)
        print(f"Exported {len(filtered_results)} results to {output_file}")
    
    def print_summary(self):
        """Print a detailed summary."""
        summary = self.get_summary()
        
        print("\n" + "="*70)
        print("RESULTS ANALYSIS")
        print("="*70)
        print(f"\nOverall Statistics:")
        print(f"  Total stores: {summary['total_stores']}")
        print(f"  Successful verifications: {summary['successful']}")
        print(f"  Failed verifications: {summary['failed']}")
        print(f"  Success rate: {summary['success_rate']}")
        
        print(f"\nFeature Detection:")
        print(f"  Multi-currency support: {summary['multi_currency']}")
        print(f"  Post-purchase upsells: {summary['post_purchase_upsells']}")
        print(f"  Reached checkout: {summary['reached_checkout']}")
        
        # Currency distribution
        currencies = self.get_currency_distribution()
        if currencies:
            print(f"\nCurrency Distribution:")
            for currency, count in sorted(currencies.items(), key=lambda x: x[1], reverse=True)[:10]:
                print(f"  {currency}: {count}")
        
        # Error distribution
        errors = self.get_error_distribution()
        if errors:
            print(f"\nTop Errors:")
            for error, count in sorted(errors.items(), key=lambda x: x[1], reverse=True)[:5]:
                error_preview = error[:60] + "..." if len(error) > 60 else error
                print(f"  [{count}x] {error_preview}")
        
        print("\n" + "="*70 + "\n")


def main():
    """Example analysis."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analyze_results.py <results_file.json>")
        print("\nExample: python analyze_results.py results/results_20260115_143022.json")
        return
    
    results_file = sys.argv[1]
    
    if not Path(results_file).exists():
        print(f"Error: File not found: {results_file}")
        return
    
    analyzer = ResultsAnalyzer(results_file)
    
    # Print summary
    analyzer.print_summary()
    
    # Example filters
    print("Example Analyses:")
    print("-" * 70)
    
    # Stores with both multi-currency and upsells
    elite_stores = analyzer.filter_by_criteria(
        multiple_currencies_supported=True,
        post_purchase_upsell_detected=True,
        success=True
    )
    print(f"\n1. Stores with BOTH multi-currency AND post-purchase upsells: {len(elite_stores)}")
    if elite_stores:
        print("   Sample stores:")
        for store in elite_stores[:5]:
            print(f"   - {store['store_url']}")
            currencies = set(store.get('country_currency_pairs', {}).values())
            print(f"     Currencies: {', '.join(currencies)}")
            if store.get('post_purchase_app_name'):
                print(f"     Post-purchase app: {store['post_purchase_app_name']}")
    
    # Stores with multi-currency only
    multi_currency_only = analyzer.filter_by_criteria(
        multiple_currencies_supported=True,
        post_purchase_upsell_detected=False,
        success=True
    )
    print(f"\n2. Stores with multi-currency but NO upsells: {len(multi_currency_only)}")
    
    # Stores with upsells only
    upsells_only = analyzer.filter_by_criteria(
        multiple_currencies_supported=False,
        post_purchase_upsell_detected=True,
        success=True
    )
    print(f"\n3. Stores with post-purchase upsells but NO multi-currency: {len(upsells_only)}")
    
    # Export elite stores
    if elite_stores:
        output_dir = Path("results")
        output_dir.mkdir(exist_ok=True)
        analyzer.export_filtered(elite_stores, "results/elite_stores.json")
        analyzer.export_filtered(elite_stores, "results/elite_stores.csv")
        print(f"\nElite stores exported to results/elite_stores.json and .csv")
    
    print("\n" + "="*70)
    print("\nCustom filtering examples:")
    print("-" * 70)
    print("""
# In Python:
from analyze_results import ResultsAnalyzer

analyzer = ResultsAnalyzer('results/results_20260115_143022.json')

# Get stores with specific currency
usd_stores = [r for r in analyzer.results 
              if 'USD' in r.get('country_currency_pairs', {}).values()]

# Get all successful verifications
successful = analyzer.filter_by_criteria(success=True)

# Get stores that reached checkout
checkout_reached = analyzer.filter_by_criteria(reached_checkout=True)

# Export any filtered results
analyzer.export_filtered(usd_stores, 'usd_stores.csv')
    """)
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
