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
from typing import Optional, List, Dict

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
    
    def _fetch_page(self, url: str) -> Optional[BeautifulSoup]:
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
    
    def _fetch_text(self, url: str) -> Optional[str]:
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
    
    # ==================== GNUSHA MESSAGE-ID METHODS ====================

    def _parse_gnusha_index(self, soup: BeautifulSoup) -> List[dict]:
        """
        Parse the gnusha.org index page for message-ID based links.

        Args:
            soup: BeautifulSoup of the index page

        Returns:
            List of message metadata dicts
        """
        messages = []

        # Find all message links - they have message-ID in href and end with /T/#t or /T/#u
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')

            # Message links contain /T/#t or /T/#u
            if '/T/#' in href:
                # Remove the /T/#t or /T/#u suffix to get the raw message URL
                message_id = href.split('/T/')[0]
                message_url = urljoin(self.PIPERMAIL_URL + '/', message_id)
                title = link.get_text(strip=True)

                if title and len(title) > 10:  # Filter out short navigation links
                    messages.append({
                        'url': message_url,
                        'title': title
                    })

        return messages
    
    def _parse_gnusha_message(self, url: str) -> Optional[dict]:
        """
        Parse an individual message from gnusha.org archive.

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

        # Try to find title from page
        title_elem = soup.find('title')
        if title_elem:
            message['title'] = title_elem.get_text(strip=True)

        # The message content is in the second pre tag (index 1)
        pre_tags = soup.find_all('pre')
        if len(pre_tags) >= 2:
            text = pre_tags[1].get_text()

            # Parse headers from the message
            from_match = re.search(r'From:\s*(.+?)(?:\n|$)', text)
            if from_match:
                # Clean up author (remove bullet characters used in emails)
                author = from_match.group(1).strip()
                author = author.replace('•', '@')  # gnusha replaces @ with •
                message['author'] = author

            date_match = re.search(r'Date:\s*(.+?)\t', text)  # Date ends with tab
            if date_match:
                message['date'] = date_match.group(1).strip()

            subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', text)
            if subject_match:
                message['title'] = subject_match.group(1).strip()

            # Get body (everything after the headers section, which ends with blank line)
            # Headers end with "In-Reply-To:" or similar, then blank line, then body
            body_match = re.search(r'\n\n(.+)', text, re.DOTALL)
            if body_match:
                body = body_match.group(1).strip()
                # Remove quoted text and signature for cleaner analysis
                # Keep first 2000 chars to avoid huge messages
                message['body'] = body[:2000]

        # Calculate drama signals
        full_text = f"{message['title']} {message['body']}"
        message['drama_signals'] = calculate_basic_drama_signals(full_text)

        return message
    
    def _fetch_recent_messages(self, limit: int = 50) -> List[dict]:
        """
        Fetch recent messages from the gnusha.org index.

        Args:
            limit: Maximum number of messages to fetch

        Returns:
            List of message dicts
        """
        logger.info(f"Fetching mailing list index: {self.PIPERMAIL_URL}")

        soup = self._fetch_page(self.PIPERMAIL_URL)
        if not soup:
            logger.warning("Could not fetch mailing list index")
            return []

        # Parse the index to get message URLs
        message_links = self._parse_gnusha_index(soup)
        logger.info(f"Found {len(message_links)} message links on index page")

        # Fetch individual messages (limit to avoid hammering the server)
        messages = []
        fetch_count = min(len(message_links), limit)

        for i, msg_link in enumerate(message_links[:fetch_count]):
            logger.info(f"Fetching message {i+1}/{fetch_count}: {msg_link['title'][:60]}...")

            msg = self._parse_gnusha_message(msg_link['url'])
            if msg:
                messages.append(msg)

        return messages
    
    # ==================== MAIN FETCH METHODS ====================
    
    def _group_into_threads(self, messages: List[dict]) -> List[dict]:
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
        Fetch mailing list data for recent messages.

        Args:
            days_back: Number of days to look back (used to calculate message limit)

        Returns:
            Dictionary containing all fetched data
        """
        since, until = get_date_range(days_back)

        logger.info(f"Fetching recent mailing list messages")

        # Fetch recent messages from the index
        # Estimate ~10-20 messages per day for bitcoin-dev
        message_limit = min(days_back * 20, 100)  # Cap at 100 to be respectful
        all_messages = self._fetch_recent_messages(limit=message_limit)

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
