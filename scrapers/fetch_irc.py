"""
IRC Log Scraper for Bitcoin Dev Drama Detector

Fetches IRC logs from gnusha.org for #bitcoin-core-dev channel.
Logs are published daily as plain text files.

Log format example:
2025-01-14 00:01:23 <username> message content here
2025-01-14 00:02:45 * username action message
"""

import os
import sys
import re
import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.utils import (
    logger,
    get_date_range,
    save_raw_data,
    calculate_basic_drama_signals
)


class IRCScraper:
    """Scraper for #bitcoin-core-dev IRC logs from gnusha.org."""
    
    BASE_URL = "https://gnusha.org/bitcoin-core-dev"
    CHANNEL = "#bitcoin-core-dev"
    
    # Regex patterns for parsing IRC logs
    # Standard message: 2025-01-14 00:01:23 <username> message
    MESSAGE_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+<([^>]+)>\s+(.+)$'
    )
    
    # Action message: 2025-01-14 00:01:23 * username does something
    ACTION_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+\*\s+(\S+)\s+(.+)$'
    )
    
    # System message (joins, parts, etc)
    SYSTEM_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+-!-\s+(.+)$'
    )
    
    def __init__(self):
        """Initialize the IRC scraper."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BitcoinDramaDetector/1.0'
        })
    
    def _get_log_url(self, date: datetime) -> str:
        """
        Get the URL for a specific date's log file.
        
        Args:
            date: The date to get logs for
        
        Returns:
            URL to the log file
        """
        date_str = date.strftime('%Y-%m-%d')
        return f"{self.BASE_URL}/{date_str}.log"
    
    def _fetch_log_file(self, date: datetime) -> str | None:
        """
        Fetch the raw log file for a specific date.
        
        Args:
            date: The date to fetch logs for
        
        Returns:
            Raw log content or None if not found
        """
        url = self._get_log_url(date)
        logger.info(f"Fetching IRC log: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 404:
                logger.warning(f"No log found for {date.strftime('%Y-%m-%d')}")
                return None
            
            response.raise_for_status()
            return response.text
            
        except requests.RequestException as e:
            logger.error(f"Error fetching IRC log: {e}")
            return None
    
    def _parse_log_line(self, line: str) -> dict | None:
        """
        Parse a single line from the IRC log.
        
        Args:
            line: A single line from the log file
        
        Returns:
            Parsed message dict or None if line doesn't match expected format
        """
        line = line.strip()
        if not line:
            return None
        
        # Try standard message format
        match = self.MESSAGE_PATTERN.match(line)
        if match:
            timestamp, username, message = match.groups()
            return {
                'type': 'message',
                'timestamp': timestamp,
                'user': username,
                'content': message
            }
        
        # Try action format
        match = self.ACTION_PATTERN.match(line)
        if match:
            timestamp, username, message = match.groups()
            return {
                'type': 'action',
                'timestamp': timestamp,
                'user': username,
                'content': message
            }
        
        # Try system message
        match = self.SYSTEM_PATTERN.match(line)
        if match:
            timestamp, message = match.groups()
            return {
                'type': 'system',
                'timestamp': timestamp,
                'user': None,
                'content': message
            }
        
        return None
    
    def parse_log(self, raw_log: str, date: datetime) -> dict:
        """
        Parse a raw IRC log into structured data.
        
        Args:
            raw_log: Raw log file content
            date: The date of the log
        
        Returns:
            Structured log data
        """
        messages = []
        participants = set()
        
        for line in raw_log.split('\n'):
            parsed = self._parse_log_line(line)
            if parsed and parsed['type'] in ('message', 'action'):
                # Add drama signals
                parsed['drama_signals'] = calculate_basic_drama_signals(parsed['content'])
                messages.append(parsed)
                
                if parsed['user']:
                    participants.add(parsed['user'])
        
        return {
            'date': date.strftime('%Y-%m-%d'),
            'channel': self.CHANNEL,
            'message_count': len(messages),
            'participant_count': len(participants),
            'participants': list(participants),
            'messages': messages
        }
    
    def _identify_threads(self, messages: list[dict]) -> list[dict]:
        """
        Attempt to identify conversation threads from messages.
        
        This is a simple heuristic approach:
        - Group messages that are replies (mention other users)
        - Group messages within short time windows on same topic
        
        Args:
            messages: List of parsed messages
        
        Returns:
            List of identified threads
        """
        threads = []
        current_thread = []
        last_timestamp = None
        
        for msg in messages:
            if msg['type'] != 'message':
                continue
            
            # Check if this continues the current thread
            # (within 5 minutes of last message)
            try:
                msg_time = datetime.strptime(msg['timestamp'], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
            
            if last_timestamp:
                time_diff = (msg_time - last_timestamp).total_seconds()
                
                # If gap > 5 minutes, start new thread
                if time_diff > 300 and current_thread:
                    if len(current_thread) >= 3:  # Only keep threads with 3+ messages
                        threads.append(self._summarize_thread(current_thread))
                    current_thread = []
            
            current_thread.append(msg)
            last_timestamp = msg_time
        
        # Don't forget the last thread
        if len(current_thread) >= 3:
            threads.append(self._summarize_thread(current_thread))
        
        return threads
    
    def _summarize_thread(self, messages: list[dict]) -> dict:
        """
        Create a summary of a conversation thread.
        
        Args:
            messages: List of messages in the thread
        
        Returns:
            Thread summary dict
        """
        participants = list(set(m['user'] for m in messages if m['user']))
        all_content = ' '.join(m['content'] for m in messages)
        
        # Aggregate drama signals
        total_drama = sum(m.get('drama_signals', {}).get('drama_keywords', 0) for m in messages)
        total_positive = sum(m.get('drama_signals', {}).get('positive_keywords', 0) for m in messages)
        nack_count = sum(1 for m in messages if m.get('drama_signals', {}).get('has_nack', False))
        ack_count = sum(1 for m in messages if m.get('drama_signals', {}).get('has_ack', False))
        
        return {
            'start_time': messages[0]['timestamp'],
            'end_time': messages[-1]['timestamp'],
            'message_count': len(messages),
            'participants': participants,
            'participant_count': len(participants),
            'first_message': messages[0]['content'][:200],
            'drama_signals': {
                'drama_keywords': total_drama,
                'positive_keywords': total_positive,
                'nack_count': nack_count,
                'ack_count': ack_count
            }
        }
    
    def fetch_date(self, date: datetime) -> dict | None:
        """
        Fetch and parse IRC logs for a specific date.
        
        Args:
            date: The date to fetch
        
        Returns:
            Parsed log data or None if no logs found
        """
        raw_log = self._fetch_log_file(date)
        
        if raw_log is None:
            return None
        
        parsed = self.parse_log(raw_log, date)
        
        # Identify conversation threads
        parsed['threads'] = self._identify_threads(parsed['messages'])
        
        logger.info(f"Parsed {parsed['message_count']} messages, {len(parsed['threads'])} threads")
        return parsed
    
    def fetch_all(self, days_back: int = 1) -> dict:
        """
        Fetch IRC logs for the specified time period.
        
        Args:
            days_back: Number of days to look back
        
        Returns:
            Dictionary containing all fetched data
        """
        since, until = get_date_range(days_back)
        
        logger.info(f"Fetching IRC logs from {since.date()} to {until.date()}")
        
        all_logs = []
        current_date = since.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current_date.date() <= until.date():
            log_data = self.fetch_date(current_date)
            if log_data:
                all_logs.append(log_data)
            current_date += timedelta(days=1)
        
        # Aggregate stats
        total_messages = sum(log['message_count'] for log in all_logs)
        total_threads = sum(len(log.get('threads', [])) for log in all_logs)
        all_participants = set()
        for log in all_logs:
            all_participants.update(log.get('participants', []))
        
        data = {
            'source': 'irc',
            'channel': self.CHANNEL,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'date_range': {
                'since': since.isoformat(),
                'until': until.isoformat()
            },
            'logs': all_logs,
            'summary': {
                'days_fetched': len(all_logs),
                'total_messages': total_messages,
                'total_threads': total_threads,
                'unique_participants': len(all_participants)
            }
        }
        
        logger.info(f"IRC fetch complete: {data['summary']}")
        return data


def main():
    """Main entry point for IRC scraper."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch IRC logs for Bitcoin Dev Drama Detector')
    parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
    args = parser.parse_args()
    
    scraper = IRCScraper()
    data = scraper.fetch_all(days_back=args.days)
    
    # Save the data
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    save_raw_data(data, 'irc', date_str)
    
    print(f"\n✅ IRC scrape complete!")
    print(f"   Days: {data['summary']['days_fetched']}")
    print(f"   Messages: {data['summary']['total_messages']}")
    print(f"   Threads: {data['summary']['total_threads']}")
    print(f"   Participants: {data['summary']['unique_participants']}")


if __name__ == '__main__':
    main()
