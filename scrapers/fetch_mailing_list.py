"""
Mailing List Scraper for Bitcoin Dev Drama Detector

Fetches messages from the bitcoin-dev mailing list.
Uses the public web archive at groups.google.com/g/bitcoindev

Note: Google Groups doesn't have a public API, so we scrape the web archive.
This is rate-limited and respectful of the service.
"""

import os
import sys
import re
import time
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.utils import (
    logger,
    get_date_range,
    save_raw_data,
    calculate_basic_drama_signals
)


class MailingListScraper:
    """Scraper for bitcoin-dev mailing list from Google Groups."""
    
    BASE_URL = "https://groups.google.com/g/bitcoindev"
    
    # Alternative: Use the public-inbox mirror which is more scrapeable
    # https://lists.linuxfoundation.org/pipermail/bitcoin-dev/
    PIPERMAIL_URL = "https://gnusha.org/pi/bitcoindev"
    
    def __init__(self, use_pipermail: bool = True):
        """
        Initialize the mailing list scraper.
        
        Args:
            use_pipermail: If True, use gnusha.org mirror (recommended)
        """
        self.use_pipermail = use_pipermail
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BitcoinDramaDetector/1.0 (research project)'
        })
        
        # Rate limiting: be nice to the servers
        self.request_delay = 1.0  # seconds between requests
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()
    
    def _fetch_page(self, url: str) -> BeautifulSoup | None:
        """
        Fetch and parse a web page.
        
        Args:
            url: URL to fetch
        
        Returns:
            BeautifulSoup object or None on error
        """
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'lxml')
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_text(self, url: str) -> str | None:
        """
        Fetch raw text content.
        
        Args:
            url: URL to fetch
        
        Returns:
            Text content or None on error
        """
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    # ==================== PIPERMAIL/GNUSHA METHODS ====================
    
    def _get_pipermail_month_url(self, year: int, month: int) -> str:
        """Get URL for a specific month's archive on gnusha.org."""
        month_name = datetime(year, month, 1).strftime('%Y-%B')
        return f"{self.PIPERMAIL_URL}/{month_name}/"
    
    def _parse_pipermail_index(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        """
        Parse the thread index page from pipermail archive.
        
        Args:
            soup: BeautifulSoup of the index page
            base_url: Base URL for resolving relative links
        
        Returns:
            List of thread metadata dicts
        """
        threads = []
        
        # Find all message links in the thread index
        # gnusha.org format has links to individual messages
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            
            # Message links typically end in .html and contain a hash
            if '.html' in href and href != 'thread.html' and href != 'date.html':
                thread_url = urljoin(base_url, href)
                title = link.get_text(strip=True)
                
                if title and len(title) > 5:  # Filter out navigation links
                    threads.append({
                        'url': thread_url,
                        'title': title
                    })
        
        return threads
    
    def _parse_pipermail_message(self, url: str) -> dict | None:
        """
        Parse an individual message from pipermail archive.
        
        Args:
            url: URL to the message
        
        Returns:
            Parsed message dict or None on error
        """
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
        
        # Try to find title
        title_elem = soup.find('title')
        if title_elem:
            message['title'] = title_elem.get_text(strip=True)
        
        # Look for the pre tag containing the message
        pre = soup.find('pre')
        if pre:
            text = pre.get_text()
            
            # Parse headers from the message
            header_match = re.search(r'From:\s*(.+?)(?:\n|$)', text)
            if header_match:
                message['author'] = header_match.group(1).strip()
            
            date_match = re.search(r'Date:\s*(.+?)(?:\n|$)', text)
            if date_match:
                message['date'] = date_match.group(1).strip()
            
            subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', text)
            if subject_match:
                message['title'] = subject_match.group(1).strip()
            
            # Get body (everything after headers)
            body_match = re.search(r'\n\n(.+)', text, re.DOTALL)
            if body_match:
                message['body'] = body_match.group(1).strip()
        
        # Calculate drama signals
        full_text = f"{message['title']} {message['body']}"
        message['drama_signals'] = calculate_basic_drama_signals(full_text)
        
        return message
    
    def _fetch_pipermail_month(self, year: int, month: int) -> list[dict]:
        """
        Fetch all messages from a specific month.
        
        Args:
            year: Year (e.g., 2025)
            month: Month (1-12)
        
        Returns:
            List of message dicts
        """
        # Try thread index first
        base_url = self._get_pipermail_month_url(year, month)
        thread_url = urljoin(base_url, 'thread.html')
        
        logger.info(f"Fetching mailing list index: {thread_url}")
        
        soup = self._fetch_page(thread_url)
        if not soup:
            # Try date index as fallback
            date_url = urljoin(base_url, 'date.html')
            soup = self._fetch_page(date_url)
            if not soup:
                logger.warning(f"Could not fetch mailing list for {year}-{month:02d}")
                return []
        
        # Parse the index to get thread URLs
        thread_links = self._parse_pipermail_index(soup, base_url)
        logger.info(f"Found {len(thread_links)} message links")
        
        # Fetch individual messages (limit to avoid hammering the server)
        messages = []
        for i, thread in enumerate(thread_links[:50]):  # Limit to 50 messages per run
            logger.debug(f"Fetching message {i+1}/{min(len(thread_links), 50)}: {thread['title'][:50]}")
            
            msg = self._parse_pipermail_message(thread['url'])
            if msg:
                messages.append(msg)
        
        return messages
    
    # ==================== MAIN FETCH METHODS ====================
    
    def _group_into_threads(self, messages: list[dict]) -> list[dict]:
        """
        Group messages into conversation threads based on subject.
        
        Args:
            messages: List of individual messages
        
        Returns:
            List of thread dicts
        """
        # Group by normalized subject (remove Re:, Fwd:, etc)
        threads_map = {}
        
        for msg in messages:
            # Normalize subject
            subject = msg.get('title', '')
            subject = re.sub(r'^(Re|Fwd|FW):\s*', '', subject, flags=re.IGNORECASE)
            subject = subject.strip().lower()
            
            if subject not in threads_map:
                threads_map[subject] = {
                    'title': msg.get('title', 'Unknown'),
                    'messages': [],
                    'participants': set(),
                    'first_date': msg.get('date'),
                    'last_date': msg.get('date'),
                }
            
            threads_map[subject]['messages'].append(msg)
            
            author = msg.get('author', '')
            if author:
                # Clean up author (extract just the name or email)
                author_clean = re.sub(r'<[^>]+>', '', author).strip()
                if author_clean:
                    threads_map[subject]['participants'].add(author_clean)
            
            threads_map[subject]['last_date'] = msg.get('date')
        
        # Convert to list and calculate thread-level stats
        threads = []
        for subject, thread_data in threads_map.items():
            # Aggregate drama signals across all messages in thread
            total_drama = sum(
                m.get('drama_signals', {}).get('drama_keywords', 0) 
                for m in thread_data['messages']
            )
            total_positive = sum(
                m.get('drama_signals', {}).get('positive_keywords', 0) 
                for m in thread_data['messages']
            )
            nack_count = sum(
                1 for m in thread_data['messages'] 
                if m.get('drama_signals', {}).get('has_nack', False)
            )
            ack_count = sum(
                1 for m in thread_data['messages'] 
                if m.get('drama_signals', {}).get('has_ack', False)
            )
            
            threads.append({
                'title': thread_data['title'],
                'message_count': len(thread_data['messages']),
                'participants': list(thread_data['participants']),
                'participant_count': len(thread_data['participants']),
                'first_date': thread_data['first_date'],
                'last_date': thread_data['last_date'],
                'messages': thread_data['messages'],
                'drama_signals': {
                    'drama_keywords': total_drama,
                    'positive_keywords': total_positive,
                    'nack_count': nack_count,
                    'ack_count': ack_count
                }
            })
        
        # Sort by message count (most active threads first)
        threads.sort(key=lambda t: t['message_count'], reverse=True)
        
        return threads
    
    def fetch_all(self, days_back: int = 1) -> dict:
        """
        Fetch mailing list data for the specified time period.
        
        Args:
            days_back: Number of days to look back
        
        Returns:
            Dictionary containing all fetched data
        """
        since, until = get_date_range(days_back)
        
        logger.info(f"Fetching mailing list data from {since.date()} to {until.date()}")
        
        # Determine which months we need to fetch
        months_to_fetch = set()
        current = since
        while current <= until:
            months_to_fetch.add((current.year, current.month))
            current += timedelta(days=32)
            current = current.replace(day=1)
        
        # Fetch messages from each month
        all_messages = []
        for year, month in sorted(months_to_fetch):
            messages = self._fetch_pipermail_month(year, month)
            all_messages.extend(messages)
        
        # Filter to just the date range we want
        # (This is approximate since we don't always have good date parsing)
        
        # Group into threads
        threads = self._group_into_threads(all_messages)
        
        # Calculate summary stats
        all_participants = set()
        for thread in threads:
            all_participants.update(thread['participants'])
        
        data = {
            'source': 'mailing_list',
            'list': 'bitcoin-dev',
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'date_range': {
                'since': since.isoformat(),
                'until': until.isoformat()
            },
            'threads': threads,
            'summary': {
                'total_threads': len(threads),
                'total_messages': len(all_messages),
                'unique_participants': len(all_participants)
            }
        }
        
        logger.info(f"Mailing list fetch complete: {data['summary']}")
        return data


def main():
    """Main entry point for mailing list scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch mailing list data for Bitcoin Dev Drama Detector')
    parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
    args = parser.parse_args()
    
    scraper = MailingListScraper()
    data = scraper.fetch_all(days_back=args.days)
    
    # Save the data
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    save_raw_data(data, 'mailing_list', date_str)
    
    print(f"\n✅ Mailing list scrape complete!")
    print(f"   Threads: {data['summary']['total_threads']}")
    print(f"   Messages: {data['summary']['total_messages']}")
    print(f"   Participants: {data['summary']['unique_participants']}")


if __name__ == '__main__':
    main()
