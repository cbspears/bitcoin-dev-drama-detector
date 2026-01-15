#!/usr/bin/env python3
"""
Fetch Historical Raw Data

Fetches raw data from GitHub, IRC, and mailing lists for historical dates.
This populates the data/raw/ directories so backfill_historical.py can analyze them.

Usage:
    python3 fetch_historical_raw.py --days 14
    python3 fetch_historical_raw.py --start 2024-01-01 --end 2024-01-31
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scrapers.fetch_irc import IRCScraper
from scrapers.fetch_mailing_list import MailingListScraper
from scrapers.utils import logger, save_raw_data
import requests


class HistoricalDataFetcher:
    """Fetch historical raw data from all sources."""

    def __init__(self, github_token=None):
        """Initialize fetcher."""
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.irc_scraper = IRCScraper()
        self.ml_scraper = MailingListScraper()

    def fetch_github_for_date(self, date):
        """
        Fetch GitHub data for a specific date.

        Fetches PRs and issues created/updated on that date.
        """
        date_str = date.strftime('%Y-%m-%d')
        logger.info(f"Fetching GitHub data for {date_str}")

        # Check if already exists
        existing_path = f"data/raw/github/{date_str}.json"
        if os.path.exists(existing_path):
            logger.info(f"  Already exists, skipping")
            return True

        try:
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'BitcoinDramaDetector/1.0'
            }
            if self.github_token:
                headers['Authorization'] = f'token {self.github_token}'

            # Fetch PRs created on this date
            next_day = date + timedelta(days=1)
            date_filter = f"{date.strftime('%Y-%m-%dT%H:%M:%SZ')}..{next_day.strftime('%Y-%m-%dT%H:%M:%SZ')}"

            pull_requests = []
            issues = []

            # Fetch PRs (limit to 100 for historical data)
            pr_url = f"https://api.github.com/repos/bitcoin/bitcoin/pulls"
            params = {
                'state': 'all',
                'sort': 'created',
                'direction': 'desc',
                'per_page': 100
            }

            response = requests.get(pr_url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                all_prs = response.json()
                # Filter by date
                for pr in all_prs:
                    created_at = datetime.strptime(pr['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                    if created_at.date() == date.date():
                        pull_requests.append({
                            'number': pr['number'],
                            'title': pr['title'],
                            'user': pr['user']['login'],
                            'state': pr['state'],
                            'created_at': pr['created_at'],
                            'updated_at': pr['updated_at'],
                            'body': pr.get('body') or '',
                            'comments': pr.get('comments', 0),
                            'url': pr['html_url']
                        })

            # Fetch issues (limit to 100)
            issue_url = f"https://api.github.com/repos/bitcoin/bitcoin/issues"
            response = requests.get(issue_url, headers=headers, params=params, timeout=30)
            if response.status_code == 200:
                all_issues = response.json()
                # Filter by date and exclude PRs
                for issue in all_issues:
                    if 'pull_request' not in issue:
                        created_at = datetime.strptime(issue['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                        if created_at.date() == date.date():
                            issues.append({
                                'number': issue['number'],
                                'title': issue['title'],
                                'user': issue['user']['login'],
                                'state': issue['state'],
                                'created_at': issue['created_at'],
                                'updated_at': issue['updated_at'],
                                'body': issue.get('body') or '',
                                'comments': issue.get('comments', 0),
                                'url': issue['html_url']
                            })

            # Save data
            data = {
                'source': 'github',
                'repository': 'bitcoin/bitcoin',
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'date': date_str,
                'pull_requests': pull_requests,
                'issues': issues,
                'summary': {
                    'pull_requests': len(pull_requests),
                    'issues': len(issues)
                }
            }

            save_raw_data(data, 'github', date_str)
            logger.info(f"  ✅ Saved {len(pull_requests)} PRs, {len(issues)} issues")
            return True

        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            return False

    def fetch_irc_for_date(self, date):
        """Fetch IRC logs for a specific date."""
        date_str = date.strftime('%Y-%m-%d')
        logger.info(f"Fetching IRC data for {date_str}")

        # Check if already exists
        existing_path = f"data/raw/irc/{date_str}.json"
        if os.path.exists(existing_path):
            logger.info(f"  Already exists, skipping")
            return True

        try:
            # Fetch log for this specific date
            log_data = self.irc_scraper.fetch_date(date)

            if log_data:
                # Wrap in expected format
                data = {
                    'source': 'irc',
                    'channel': '#bitcoin-core-dev',
                    'fetched_at': datetime.now(timezone.utc).isoformat(),
                    'date_range': {
                        'since': date.isoformat(),
                        'until': date.isoformat()
                    },
                    'logs': [log_data],
                    'summary': {
                        'days_fetched': 1,
                        'total_messages': log_data['message_count'],
                        'total_threads': len(log_data.get('threads', [])),
                        'unique_participants': log_data['participant_count']
                    }
                }

                save_raw_data(data, 'irc', date_str)
                logger.info(f"  ✅ Saved {log_data['message_count']} messages")
                return True
            else:
                logger.warning(f"  ⊘ No IRC log available")
                return False

        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            return False

    def fetch_mailing_list_for_date(self, date):
        """
        Fetch mailing list data for a specific date.

        Note: Mailing list scraper currently fetches recent messages.
        For historical data, we'd need to enhance it.
        For now, we'll skip or use a placeholder.
        """
        date_str = date.strftime('%Y-%m-%d')
        logger.info(f"Fetching mailing list data for {date_str}")

        # Check if already exists
        existing_path = f"data/raw/mailing_list/{date_str}.json"
        if os.path.exists(existing_path):
            logger.info(f"  Already exists, skipping")
            return True

        # For MVP: Skip mailing list historical fetch
        # This would require date-based filtering of the archive
        logger.info(f"  ⊘ Skipping (mailing list historical fetch not yet implemented)")
        return False

    def fetch_date_range(self, start_date, end_date):
        """Fetch data for a range of dates."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Fetching historical data: {start_date.date()} to {end_date.date()}")
        logger.info(f"{'='*60}\n")

        current = start_date
        success_count = 0
        total_days = (end_date - start_date).days + 1

        while current <= end_date:
            logger.info(f"\n--- {current.strftime('%Y-%m-%d')} ---")

            # Fetch from all sources
            github_ok = self.fetch_github_for_date(current)
            irc_ok = self.fetch_irc_for_date(current)
            ml_ok = self.fetch_mailing_list_for_date(current)

            if github_ok or irc_ok or ml_ok:
                success_count += 1

            current += timedelta(days=1)

        logger.info(f"\n{'='*60}")
        logger.info(f"Fetch complete: {success_count}/{total_days} days")
        logger.info(f"{'='*60}")

        return success_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch historical raw data for backfill',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to fetch (from today backwards)'
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
        '--github-token',
        type=str,
        help='GitHub token (or set GITHUB_TOKEN env var)'
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

    # Fetch data
    try:
        fetcher = HistoricalDataFetcher(github_token=args.github_token)
        success_count = fetcher.fetch_date_range(start_date, end_date)

        if success_count > 0:
            print(f"\n✅ Successfully fetched data for {success_count} days")
            print(f"\nNext step: Run backfill analysis")
            print(f"  python3 backfill_historical.py --days {args.days}")
            sys.exit(0)
        else:
            print(f"\n❌ No data fetched")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\nFetch interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.exception("Fetch failed")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
