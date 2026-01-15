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

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
            with open(output_path, 'r') as f:
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
            with open(output_path, 'r') as f:
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


def main():
    parser = argparse.ArgumentParser(description='Fetch historical data for Bitcoin Dev Drama Detector')
    parser.add_argument('--source', type=str, choices=['irc', 'mailing_list', 'all'],
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

    print("\nHistorical fetch complete!")


if __name__ == '__main__':
    main()
