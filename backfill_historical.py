#!/usr/bin/env python3
"""
Backfill Historical Drama Data

Fetches and analyzes historical Bitcoin development data to build
a complete drama timeline.

Usage:
    python3 backfill_historical.py --days 14          # Last 14 days
    python3 backfill_historical.py --start 2024-01-01 --end 2024-01-31
    python3 backfill_historical.py --days 90 --dry-run  # Estimate cost only
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analyzer.drama_scorer import DramaScorer
from scrapers.utils import logger, save_raw_data, load_raw_data


class HistoricalBackfill:
    """Backfill historical drama data."""

    def __init__(self, api_key=None):
        """Initialize backfill processor."""
        self.scorer = DramaScorer(api_key=api_key)
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0
        self.total_api_calls = 0

    def estimate_cost(self, start_date, end_date, items_per_day=30):
        """
        Estimate API cost for backfill.

        Args:
            start_date: Start date
            end_date: End date
            items_per_day: Number of items to analyze per day

        Returns:
            Dict with cost estimates
        """
        days = (end_date - start_date).days + 1
        total_items = days * items_per_day

        # Claude Sonnet 4 pricing (approximate)
        # Input: ~$3 per million tokens
        # Output: ~$15 per million tokens
        # Average: ~500 input tokens + 200 output tokens per analysis
        # Cost: ~$0.01 per item

        cost_per_item = 0.01
        estimated_cost = total_items * cost_per_item

        return {
            'days': days,
            'items_per_day': items_per_day,
            'total_items': total_items,
            'estimated_cost': estimated_cost,
            'cost_per_day': estimated_cost / days
        }

    def check_existing(self, date_str):
        """Check if data already exists for this date."""
        daily_scores_path = f"data/processed/daily_scores_{date_str}.json"
        return os.path.exists(daily_scores_path)

    def fetch_github_historical(self, date_str):
        """
        Fetch GitHub data for a specific historical date.

        Note: For now, we'll use the existing scraper which gets recent data.
        In a full implementation, we'd modify the scraper to accept date ranges.
        """
        logger.info(f"Fetching GitHub data for {date_str}")

        try:
            # For now, just use existing data if available
            existing = load_raw_data('github', date_str)
            if existing:
                logger.info(f"  Using existing GitHub data")
                return existing

            # If no existing data, we'd need to fetch it
            # For MVP: skip if data doesn't exist
            logger.warning(f"  No existing GitHub data for {date_str}")
            return None

        except Exception as e:
            logger.error(f"  Error fetching GitHub data: {e}")
            return None

    def fetch_irc_historical(self, date_str):
        """
        Fetch IRC logs for a specific historical date.

        IRC logs are available at: https://gnusha.org/bitcoin-core-dev/YYYY-MM-DD.log
        We can fetch these directly.
        """
        logger.info(f"Fetching IRC data for {date_str}")

        try:
            # Check if we already have it
            existing = load_raw_data('irc', date_str)
            if existing:
                logger.info(f"  Using existing IRC data")
                return existing

            # Fetch from gnusha.org (implemented in fetch_irc.py)
            # For MVP: use subprocess to call existing scraper
            # In full implementation: modify scraper to accept --date parameter

            logger.warning(f"  No existing IRC data for {date_str}")
            return None

        except Exception as e:
            logger.error(f"  Error fetching IRC data: {e}")
            return None

    def fetch_mailing_list_historical(self, date_str):
        """Fetch mailing list data for a specific historical date."""
        logger.info(f"Fetching mailing list data for {date_str}")

        try:
            existing = load_raw_data('mailing_list', date_str)
            if existing:
                logger.info(f"  Using existing mailing list data")
                return existing

            logger.warning(f"  No existing mailing list data for {date_str}")
            return None

        except Exception as e:
            logger.error(f"  Error fetching mailing list data: {e}")
            return None

    def analyze_date(self, date_str):
        """
        Analyze drama for a specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            Analysis result dict
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing {date_str}")
        logger.info(f"{'='*60}")

        try:
            # Fetch data from all sources
            github_data = self.fetch_github_historical(date_str)
            irc_data = self.fetch_irc_historical(date_str)
            ml_data = self.fetch_mailing_list_historical(date_str)

            # Count what we have
            has_data = []
            if github_data:
                has_data.append('GitHub')
            if irc_data:
                has_data.append('IRC')
            if ml_data:
                has_data.append('Mailing List')

            if not has_data:
                logger.warning(f"No data available for {date_str} - skipping")
                return None

            logger.info(f"Data sources: {', '.join(has_data)}")

            # Run analysis
            result = self.scorer.process_all_data(date_str)

            # Track API calls
            self.total_api_calls += 30  # Approximate

            return result

        except Exception as e:
            logger.error(f"Error analyzing {date_str}: {e}")
            raise

    def backfill(self, start_date, end_date, dry_run=False, skip_existing=True, auto_confirm=False):
        """
        Backfill historical data for a date range.

        Args:
            start_date: Start date (datetime)
            end_date: End date (datetime)
            dry_run: If True, only estimate cost without processing
            skip_existing: If True, skip dates that already have data
            auto_confirm: If True, skip confirmation prompt

        Returns:
            Summary dict
        """
        # Estimate cost
        estimate = self.estimate_cost(start_date, end_date)

        print("\n" + "="*60)
        print("HISTORICAL BACKFILL")
        print("="*60)
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        print(f"Days to process: {estimate['days']}")
        print(f"Items per day: {estimate['items_per_day']}")
        print(f"Total API calls: ~{estimate['total_items']}")
        print(f"Estimated cost: ${estimate['estimated_cost']:.2f}")
        print(f"Cost per day: ${estimate['cost_per_day']:.2f}")
        print("="*60)

        if dry_run:
            print("\n[DRY RUN] No data will be processed.")
            return estimate

        # Confirm before proceeding
        if not auto_confirm:
            print("\nThis will:")
            print("1. Fetch historical data from GitHub, IRC, and mailing lists")
            print("2. Analyze drama using Claude Sonnet 4 API")
            print("3. Save results to data/processed/")
            print(f"4. Cost approximately ${estimate['estimated_cost']:.2f}")
            print("\nContinue? (yes/no): ", end='')

            confirmation = input().strip().lower()
            if confirmation not in ['yes', 'y']:
                print("Backfill cancelled.")
                return None

        print("\nStarting backfill...")

        # Process each date
        current = start_date
        results = []

        while current <= end_date:
            date_str = current.strftime('%Y-%m-%d')

            # Check if already exists
            if skip_existing and self.check_existing(date_str):
                logger.info(f"Skipping {date_str} (already exists)")
                self.skipped_count += 1
                current += timedelta(days=1)
                continue

            try:
                result = self.analyze_date(date_str)

                if result:
                    self.processed_count += 1
                    results.append(result)

                    # Print summary
                    scores = result['daily_scores']
                    print(f"\n✅ {date_str}")
                    print(f"   Overall: {scores['overall']:.1f}/10")
                    print(f"   GitHub: {scores['github']:.1f}/10")
                    print(f"   IRC: {scores['irc']:.1f}/10")
                    print(f"   Mailing List: {scores['mailing_list']:.1f}/10")
                else:
                    self.skipped_count += 1
                    print(f"\n⊘ {date_str} - No data available")

            except Exception as e:
                self.error_count += 1
                logger.error(f"❌ {date_str} - Error: {e}")

            current += timedelta(days=1)

        # Final summary
        print("\n" + "="*60)
        print("BACKFILL COMPLETE")
        print("="*60)
        print(f"Processed: {self.processed_count} days")
        print(f"Skipped: {self.skipped_count} days")
        print(f"Errors: {self.error_count} days")
        print(f"API calls: ~{self.total_api_calls}")
        print(f"Actual cost: ~${self.total_api_calls * 0.01:.2f}")
        print("="*60)

        return {
            'processed': self.processed_count,
            'skipped': self.skipped_count,
            'errors': self.error_count,
            'api_calls': self.total_api_calls,
            'results': results
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Backfill historical drama data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with last 14 days
  python3 backfill_historical.py --days 14

  # Specific date range
  python3 backfill_historical.py --start 2024-01-01 --end 2024-01-31

  # Dry run (estimate cost only)
  python3 backfill_historical.py --days 90 --dry-run

  # Full 2 years
  python3 backfill_historical.py --days 730
        """
    )

    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to backfill (from today backwards)'
    )
    parser.add_argument(
        '--start',
        type=str,
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--end',
        type=str,
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Estimate cost without processing'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Reprocess existing dates'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        help='Anthropic API key (or set ANTHROPIC_API_KEY env var)'
    )
    parser.add_argument(
        '--yes', '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )

    args = parser.parse_args()

    # Determine date range
    if args.days:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=args.days - 1)
    elif args.start and args.end:
        start_date = datetime.strptime(args.start, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        end_date = datetime.strptime(args.end, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    else:
        parser.error("Must specify either --days or both --start and --end")

    # Run backfill
    try:
        backfill = HistoricalBackfill(api_key=args.api_key)
        result = backfill.backfill(
            start_date,
            end_date,
            dry_run=args.dry_run,
            skip_existing=not args.force,
            auto_confirm=args.yes
        )

        if result:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nBackfill interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception("Backfill failed")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
