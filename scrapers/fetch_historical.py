"""
Historical Data Fetcher for Bitcoin Dev Drama Detector

Fetches historical data from IRC logs and mailing list archives on gnusha.org.
Unlike the regular scrapers that fetch recent data, this script fetches
data for specific date ranges in the past.

Usage:
    python fetch_historical.py --source irc --start 2025-01-01 --end 2025-12-31
    python fetch_historical.py --source mailing_list --start 2025-01-01 --end 2025-12-31
    python fetch_historical.py --source all --start 2025-01-01 --end 2025-12-31
"""

import os
import sys
import re
import json
import time
import argparse
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from typing import Optional, List, Dict
from dotenv import load_dotenv

# Load environment variables from project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

# Add parent directory to path for imports
sys.path.insert(0, project_root)

from scrapers.utils import logger, save_raw_data, calculate_basic_drama_signals
from scrapers.fetch_irc import IRCScraper


class HistoricalMailingListScraper:
    """Fetch historical mailing list data from gnusha.org/pi/bitcoindev archives."""

    BASE_URL = "https://gnusha.org/pi/bitcoindev"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BitcoinDramaDetector/1.0 (research project)'
        })
        self.request_delay = 1.0
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch and parse a web page."""
        self._rate_limit()
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def _parse_index_page(self, soup: BeautifulSoup) -> tuple[List[dict], Optional[str]]:
        """
        Parse an index page for messages and the next page link.

        Returns:
            Tuple of (messages list, next_page_timestamp or None)
        """
        messages = []
        next_timestamp = None

        # Find all message entries - look for links to threads
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')

            # Thread links contain /T/#
            if '/T/#' in href:
                message_id = href.split('/T/')[0].lstrip('/')
                title = link.get_text(strip=True)

                if title and len(title) > 5:
                    # Try to find the date from surrounding text
                    parent = link.find_parent(['pre', 'div', 'p'])
                    date_str = None
                    if parent:
                        text = parent.get_text()
                        # Look for UTC timestamp pattern
                        date_match = re.search(r'(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}', text)
                        if date_match:
                            date_str = date_match.group(1)

                    messages.append({
                        'message_id': message_id,
                        'title': title,
                        'date': date_str,
                        'url': f"{self.BASE_URL}/{message_id}"
                    })

        # Find "next (older)" link for pagination
        for link in soup.find_all('a', href=True):
            if 'next' in link.get_text().lower() or 'older' in link.get_text().lower():
                href = link.get('href', '')
                # Extract timestamp parameter
                match = re.search(r'\?t=(\d+)', href)
                if match:
                    next_timestamp = match.group(1)
                    break

        return messages, next_timestamp

    def _parse_message(self, url: str) -> Optional[dict]:
        """Parse an individual message."""
        soup = self._fetch_page(url)
        if not soup:
            return None

        message = {
            'url': url,
            'title': '',
            'author': '',
            'date': '',
            'body': '',
        }

        # Get title
        title_elem = soup.find('title')
        if title_elem:
            message['title'] = title_elem.get_text(strip=True)

        # Parse headers from pre tag
        pre_tags = soup.find_all('pre')
        if len(pre_tags) >= 2:
            text = pre_tags[1].get_text()

            from_match = re.search(r'From:\s*(.+?)(?:\n|$)', text)
            if from_match:
                author = from_match.group(1).strip().replace('•', '@')
                message['author'] = author

            date_match = re.search(r'Date:\s*(.+?)(?:\t|\n)', text)
            if date_match:
                message['date'] = date_match.group(1).strip()

            subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', text)
            if subject_match:
                message['title'] = subject_match.group(1).strip()

            body_match = re.search(r'\n\n(.+)', text, re.DOTALL)
            if body_match:
                message['body'] = body_match.group(1).strip()[:2000]

        full_text = f"{message['title']} {message['body']}"
        message['drama_signals'] = calculate_basic_drama_signals(full_text)

        return message

    def fetch_messages_for_date(self, target_date: datetime, max_messages: int = 50) -> List[dict]:
        """
        Fetch messages from around a specific date.

        Args:
            target_date: The date to fetch messages for
            max_messages: Maximum messages to fetch

        Returns:
            List of messages from around that date
        """
        logger.info(f"Fetching mailing list messages for {target_date.strftime('%Y-%m-%d')}")

        # Start from the target date (converted to timestamp format)
        # gnusha uses YYYYMMDDHHMMSS format
        start_timestamp = target_date.strftime('%Y%m%d235959')

        messages = []
        current_url = f"{self.BASE_URL}/?t={start_timestamp}"
        pages_fetched = 0
        max_pages = 10  # Limit pagination

        target_date_str = target_date.strftime('%Y-%m-%d')
        day_before = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')

        while pages_fetched < max_pages and len(messages) < max_messages:
            soup = self._fetch_page(current_url)
            if not soup:
                break

            page_messages, next_timestamp = self._parse_index_page(soup)
            pages_fetched += 1

            # Filter messages for our target date
            for msg in page_messages:
                if msg.get('date') == target_date_str:
                    messages.append(msg)
                elif msg.get('date') and msg.get('date') < day_before:
                    # We've gone past our target date, stop
                    next_timestamp = None
                    break

            if not next_timestamp:
                break

            current_url = f"{self.BASE_URL}/?t={next_timestamp}"

        # Fetch full content for each message
        full_messages = []
        for msg_meta in messages[:max_messages]:
            logger.info(f"  Fetching: {msg_meta['title'][:50]}...")
            full_msg = self._parse_message(msg_meta['url'])
            if full_msg:
                full_messages.append(full_msg)

        return full_messages

    def fetch_date(self, date: datetime) -> dict:
        """
        Fetch mailing list data for a specific date.

        Args:
            date: The date to fetch

        Returns:
            Structured data for that date
        """
        messages = self.fetch_messages_for_date(date)

        # Group into threads
        threads_map = {}
        for msg in messages:
            subject = re.sub(r'^(Re|Fwd|FW):\s*', '', msg.get('title', ''), flags=re.IGNORECASE)
            subject = subject.strip().lower()

            if subject not in threads_map:
                threads_map[subject] = {
                    'title': msg.get('title', 'Unknown'),
                    'messages': [],
                    'participants': set(),
                }

            threads_map[subject]['messages'].append(msg)
            author = msg.get('author', '')
            if author:
                author_clean = re.sub(r'<[^>]+>', '', author).strip()
                if author_clean:
                    threads_map[subject]['participants'].add(author_clean)

        threads = []
        for subject, thread_data in threads_map.items():
            total_drama = sum(m.get('drama_signals', {}).get('drama_keywords', 0) for m in thread_data['messages'])
            threads.append({
                'title': thread_data['title'],
                'message_count': len(thread_data['messages']),
                'participants': list(thread_data['participants']),
                'messages': thread_data['messages'],
                'drama_signals': {'drama_keywords': total_drama}
            })

        all_participants = set()
        for thread in threads:
            all_participants.update(thread['participants'])

        return {
            'source': 'mailing_list',
            'list': 'bitcoin-dev',
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'date': date.strftime('%Y-%m-%d'),
            'threads': threads,
            'summary': {
                'total_threads': len(threads),
                'total_messages': len(messages),
                'unique_participants': len(all_participants)
            }
        }


def fetch_historical_irc(start_date: datetime, end_date: datetime) -> None:
    """Fetch historical IRC logs for a date range."""
    scraper = IRCScraper()
    current_date = start_date

    total_days = (end_date - start_date).days + 1
    processed = 0

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        output_path = f"data/raw/irc/{date_str}.json"

        # Check if we already have this file with real data
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if existing.get('summary', {}).get('total_messages', 0) > 0:
                    logger.info(f"IRC {date_str}: Already has data, skipping")
                    current_date += timedelta(days=1)
                    processed += 1
                    continue

        logger.info(f"IRC [{processed+1}/{total_days}] Fetching {date_str}...")

        data = scraper.fetch_date(current_date)

        if data:
            # Wrap single day data in the expected format
            wrapped_data = {
                'source': 'irc',
                'channel': '#bitcoin-core-dev',
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'date': date_str,
                'logs': [data],
                'summary': {
                    'days_fetched': 1,
                    'total_messages': data.get('message_count', 0),
                    'total_threads': len(data.get('threads', [])),
                    'unique_participants': data.get('participant_count', 0)
                }
            }
            save_raw_data(wrapped_data, 'irc', date_str)
            logger.info(f"  -> {data.get('message_count', 0)} messages, {len(data.get('threads', []))} threads")
        else:
            # Save empty file to indicate we tried
            empty_data = {
                'source': 'irc',
                'channel': '#bitcoin-core-dev',
                'fetched_at': datetime.now(timezone.utc).isoformat(),
                'date': date_str,
                'logs': [],
                'summary': {
                    'days_fetched': 0,
                    'total_messages': 0,
                    'total_threads': 0,
                    'unique_participants': 0
                }
            }
            save_raw_data(empty_data, 'irc', date_str)
            logger.info(f"  -> No logs found")

        current_date += timedelta(days=1)
        processed += 1

    logger.info(f"IRC historical fetch complete: {processed} days processed")


def fetch_historical_mailing_list(start_date: datetime, end_date: datetime) -> None:
    """Fetch historical mailing list data for a date range."""
    scraper = HistoricalMailingListScraper()
    current_date = start_date

    total_days = (end_date - start_date).days + 1
    processed = 0

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        output_path = f"data/raw/mailing_list/{date_str}.json"

        # Check if we already have this file with real data
        if os.path.exists(output_path):
            with open(output_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
                if existing.get('summary', {}).get('total_messages', 0) > 0:
                    logger.info(f"Mailing list {date_str}: Already has data, skipping")
                    current_date += timedelta(days=1)
                    processed += 1
                    continue

        logger.info(f"Mailing list [{processed+1}/{total_days}] Fetching {date_str}...")

        data = scraper.fetch_date(current_date)
        save_raw_data(data, 'mailing_list', date_str)

        msg_count = data.get('summary', {}).get('total_messages', 0)
        thread_count = data.get('summary', {}).get('total_threads', 0)
        logger.info(f"  -> {msg_count} messages, {thread_count} threads")

        current_date += timedelta(days=1)
        processed += 1

    logger.info(f"Mailing list historical fetch complete: {processed} days processed")


class HistoricalGitHubScraper:
    """Fetch historical GitHub data using the Search API."""

    BASE_URL = "https://api.github.com"
    REPOS = ["bitcoin/bitcoin", "bitcoin/bips"]

    def __init__(self, token: str = None):
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'BitcoinDramaDetector/1.0'
        })
        if self.token:
            self.session.headers['Authorization'] = f'token {self.token}'
            logger.info("GitHub token configured for historical fetch")
        else:
            logger.warning("No GitHub token - rate limits will be very strict for Search API")

        self.request_delay = 2.0  # Search API has stricter rate limits
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _request(self, endpoint: str, params: dict = None, max_retries: int = 3) -> Optional[dict]:
        """Make a request to the GitHub API with retry logic."""
        self._rate_limit()
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(url, params=params)

                # Check rate limits
                remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

                if remaining < 5:
                    wait_time = max(reset_time - time.time(), 60)
                    logger.warning(f"Rate limit low ({remaining}). Waiting {wait_time:.0f}s")
                    time.sleep(wait_time)

                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    wait_time = max(reset_time - time.time(), 60)
                    logger.error(f"Rate limited. Waiting {wait_time:.0f}s")
                    time.sleep(wait_time)
                    continue

                if response.status_code in (502, 503, 504):
                    if attempt < max_retries:
                        wait_time = (2 ** attempt) * 5
                        logger.warning(f"Server error {response.status_code}. Retrying in {wait_time}s")
                        time.sleep(wait_time)
                        continue

                if response.status_code == 422:
                    logger.warning(f"Validation error: {response.text}")
                    return None

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                if attempt < max_retries:
                    wait_time = (2 ** attempt) * 5
                    logger.warning(f"Request error: {e}. Retrying in {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {max_retries} retries: {e}")
                    return None

        return None

    def search_issues_for_date(self, repo: str, date: datetime, item_type: str = 'pr') -> List[dict]:
        """
        Search for PRs or issues created on a specific date.

        Args:
            repo: Repository (e.g., 'bitcoin/bitcoin')
            date: The date to search for
            item_type: 'pr' or 'issue'

        Returns:
            List of items found
        """
        date_str = date.strftime('%Y-%m-%d')
        type_filter = 'pr' if item_type == 'pr' else 'issue'

        # Search query: repo:bitcoin/bitcoin is:pr created:2025-06-15
        query = f"repo:{repo} is:{type_filter} created:{date_str}"

        params = {
            'q': query,
            'sort': 'created',
            'order': 'desc',
            'per_page': 100
        }

        result = self._request('/search/issues', params)
        if result and 'items' in result:
            return result['items']
        return []

    def fetch_item_details(self, item: dict, repo: str) -> dict:
        """Fetch additional details for a PR or issue."""
        number = item.get('number')
        is_pr = 'pull_request' in item

        # Basic info from search result
        details = {
            'number': number,
            'title': item.get('title', ''),
            'body': item.get('body', '') or '',
            'state': item.get('state', ''),
            'user': item.get('user', {}).get('login', ''),
            'created_at': item.get('created_at', ''),
            'updated_at': item.get('updated_at', ''),
            'comments': item.get('comments', 0),
            'url': item.get('html_url', ''),
            'labels': [l.get('name', '') for l in item.get('labels', [])]
        }

        # Fetch comments if there are any (limit to reduce API calls)
        if details['comments'] > 0 and details['comments'] <= 20:
            comments_url = f"/repos/{repo}/issues/{number}/comments"
            comments_data = self._request(comments_url, {'per_page': 20})
            if comments_data:
                details['comment_list'] = [
                    {
                        'user': c.get('user', {}).get('login', ''),
                        'body': c.get('body', '') or '',
                        'created_at': c.get('created_at', '')
                    }
                    for c in comments_data[:20]
                ]

        return details

    def fetch_date(self, date: datetime, repo: str = "bitcoin/bitcoin") -> dict:
        """
        Fetch all GitHub activity for a specific date.

        Args:
            date: The date to fetch
            repo: Repository to fetch from

        Returns:
            Structured data for that date
        """
        date_str = date.strftime('%Y-%m-%d')
        logger.info(f"Searching GitHub {repo} for {date_str}...")

        # Search for PRs
        prs_raw = self.search_issues_for_date(repo, date, 'pr')
        logger.info(f"  Found {len(prs_raw)} PRs")

        # Search for issues
        issues_raw = self.search_issues_for_date(repo, date, 'issue')
        logger.info(f"  Found {len(issues_raw)} issues")

        # Fetch details for each (limit to avoid rate limits)
        pull_requests = []
        for pr in prs_raw[:30]:  # Limit to 30 PRs per day
            details = self.fetch_item_details(pr, repo)
            pull_requests.append(details)

        issues = []
        for issue in issues_raw[:30]:  # Limit to 30 issues per day
            details = self.fetch_item_details(issue, repo)
            issues.append(details)

        return {
            'source': 'github',
            'repository': repo,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'date': date_str,
            'pull_requests': pull_requests,
            'issues': issues,
            'summary': {
                'pull_requests': len(pull_requests),
                'issues': len(issues)
            }
        }


def fetch_historical_github(start_date: datetime, end_date: datetime, repo: str = "bitcoin/bitcoin") -> None:
    """Fetch historical GitHub data for a date range."""
    scraper = HistoricalGitHubScraper()
    current_date = start_date

    total_days = (end_date - start_date).days + 1
    processed = 0

    # Determine output directory based on repo
    if repo == "bitcoin/bips":
        source_name = "bips"
    else:
        source_name = "github"

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        output_path = f"data/raw/{source_name}/{date_str}.json"

        # Check if we already have this file with real data
        if os.path.exists(output_path):
            try:
                with open(output_path, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                    pr_count = len(existing.get('pull_requests', []))
                    issue_count = len(existing.get('issues', []))
                    if pr_count > 0 or issue_count > 0:
                        logger.info(f"GitHub {date_str}: Already has data ({pr_count} PRs, {issue_count} issues), skipping")
                        current_date += timedelta(days=1)
                        processed += 1
                        continue
            except (json.JSONDecodeError, IOError):
                pass

        logger.info(f"GitHub [{processed+1}/{total_days}] Fetching {date_str}...")

        data = scraper.fetch_date(current_date, repo)
        save_raw_data(data, source_name, date_str)

        pr_count = data.get('summary', {}).get('pull_requests', 0)
        issue_count = data.get('summary', {}).get('issues', 0)
        logger.info(f"  -> {pr_count} PRs, {issue_count} issues")

        current_date += timedelta(days=1)
        processed += 1

    logger.info(f"GitHub historical fetch complete: {processed} days processed")


def main():
    parser = argparse.ArgumentParser(description='Fetch historical data for Bitcoin Dev Drama Detector')
    parser.add_argument('--source', type=str, choices=['irc', 'mailing_list', 'github', 'bips', 'all'],
                        default='all', help='Which source to fetch')
    parser.add_argument('--start', type=str, required=True,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True,
                        help='End date (YYYY-MM-DD)')

    args = parser.parse_args()

    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    print(f"\n{'='*60}")
    print(f"Historical Data Fetch")
    print(f"Source: {args.source}")
    print(f"Date range: {args.start} to {args.end}")
    print(f"Total days: {(end_date - start_date).days + 1}")
    print(f"{'='*60}\n")

    if args.source in ['irc', 'all']:
        print("\n[IRC] Fetching IRC logs...\n")
        fetch_historical_irc(start_date, end_date)

    if args.source in ['mailing_list', 'all']:
        print("\n[ML] Fetching mailing list archives...\n")
        fetch_historical_mailing_list(start_date, end_date)

    if args.source in ['github', 'all']:
        print("\n[GH] Fetching GitHub (bitcoin/bitcoin) history...\n")
        fetch_historical_github(start_date, end_date, repo="bitcoin/bitcoin")

    if args.source in ['bips', 'all']:
        print("\n[BIPs] Fetching GitHub (bitcoin/bips) history...\n")
        fetch_historical_github(start_date, end_date, repo="bitcoin/bips")

    print("\nHistorical fetch complete!")


if __name__ == '__main__':
    main()
