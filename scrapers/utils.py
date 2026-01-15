"""
Shared utilities for Bitcoin Dev Drama Detector scrapers.
"""

import os
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('drama-detector')

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / 'data'
RAW_DATA_DIR = DATA_DIR / 'raw'
PROCESSED_DATA_DIR = DATA_DIR / 'processed'

# Ensure directories exist
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_date_range(days_back: int = 1) -> tuple[datetime, datetime]:
    """
    Get the date range for scraping.
    
    Args:
        days_back: Number of days to look back (default 1 for daily sync)
    
    Returns:
        Tuple of (start_date, end_date) in UTC
    """
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days_back)
    return start_date, end_date


def save_raw_data(data: dict | list, source: str, date_str: str = None) -> Path:
    """
    Save raw scraped data to JSON file.
    
    Args:
        data: The data to save
        source: Source identifier ('github', 'mailing_list', 'irc')
        date_str: Optional date string (defaults to today)
    
    Returns:
        Path to saved file
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    source_dir = RAW_DATA_DIR / source
    source_dir.mkdir(parents=True, exist_ok=True)
    
    filepath = source_dir / f'{date_str}.json'
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    logger.info(f"Saved raw data to {filepath}")
    return filepath


def load_raw_data(source: str, date_str: str) -> dict | list | None:
    """
    Load raw data for a specific source and date.
    
    Args:
        source: Source identifier ('github', 'mailing_list', 'irc')
        date_str: Date string (YYYY-MM-DD)
    
    Returns:
        Loaded data or None if not found
    """
    filepath = RAW_DATA_DIR / source / f'{date_str}.json'
    
    if not filepath.exists():
        logger.warning(f"No data found at {filepath}")
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_processed_data(data: dict | list, filename: str) -> Path:
    """
    Save processed data to the processed directory.
    
    Args:
        data: The processed data to save
        filename: Name of the file (e.g., 'daily_scores.json')
    
    Returns:
        Path to saved file
    """
    filepath = PROCESSED_DATA_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str, ensure_ascii=False)
    
    logger.info(f"Saved processed data to {filepath}")
    return filepath


def load_processed_data(filename: str) -> dict | list | None:
    """
    Load processed data.
    
    Args:
        filename: Name of the file to load
    
    Returns:
        Loaded data or None if not found
    """
    filepath = PROCESSED_DATA_DIR / filename
    
    if not filepath.exists():
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


# Drama-related keywords that might indicate controversy
DRAMA_KEYWORDS = [
    # Strong disagreement
    'nack', 'oppose', 'reject', 'disagree', 'wrong', 'bad idea',
    'dangerous', 'reckless', 'irresponsible',
    
    # Activation debates
    'uasf', 'uahf', 'hard fork', 'soft fork', 'contentious',
    'lot=true', 'lot=false', 'bip8', 'bip9', 'speedy trial',
    'activation', 'flag day',
    
    # Historical drama references
    'block size', 'segwit', 'blockstream', 'bitcoin cash',
    'bcash', 'big blocks', 'small blocks',
    
    # Process concerns
    'rushed', 'premature', 'not ready', 'needs more review',
    'insufficient testing', 'breaking change',
    
    # Personal/political
    'agenda', 'captured', 'censorship', 'attack',
    'bad actor', 'malicious', 'hostile'
]

# Positive/constructive keywords
POSITIVE_KEYWORDS = [
    'ack', 'utack', 'tested', 'lgtm', 'concept ack',
    'approach ack', 'code review', 'nit:', 'suggestion:',
    'agree', 'good point', 'makes sense', 'well explained'
]


def calculate_basic_drama_signals(text: str) -> dict:
    """
    Calculate basic drama signals from text content.
    
    This is a simple keyword-based approach. The actual drama scoring
    will use Claude API for more sophisticated analysis.
    
    Args:
        text: The text to analyze
    
    Returns:
        Dict with drama signal counts
    """
    text_lower = text.lower()
    
    drama_count = sum(1 for kw in DRAMA_KEYWORDS if kw in text_lower)
    positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text_lower)
    
    return {
        'drama_keywords': drama_count,
        'positive_keywords': positive_count,
        'text_length': len(text),
        'has_nack': 'nack' in text_lower,
        'has_ack': 'ack' in text_lower and 'nack' not in text_lower,
    }


def format_iso_date(dt: datetime) -> str:
    """Format datetime to ISO string."""
    return dt.strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso_date(date_str: str) -> datetime:
    """Parse ISO date string to datetime."""
    # Handle various formats
    for fmt in ['%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d']:
        try:
            dt = datetime.strptime(date_str.replace('+00:00', 'Z'), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    raise ValueError(f"Unable to parse date: {date_str}")
