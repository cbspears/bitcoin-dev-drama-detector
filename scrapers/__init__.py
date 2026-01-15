"""
Bitcoin Dev Drama Detector - Scrapers Package

This package contains scrapers for fetching data from Bitcoin developer
communication channels:

- fetch_github.py: GitHub API scraper for bitcoin/bitcoin repo
- fetch_irc.py: IRC log scraper for #bitcoin-core-dev
- fetch_mailing_list.py: Mailing list scraper for bitcoin-dev
- utils.py: Shared utilities and helper functions
"""

from .utils import (
    logger,
    get_date_range,
    save_raw_data,
    load_raw_data,
    save_processed_data,
    load_processed_data,
    calculate_basic_drama_signals,
    DRAMA_KEYWORDS,
    POSITIVE_KEYWORDS,
)

__all__ = [
    'logger',
    'get_date_range',
    'save_raw_data',
    'load_raw_data',
    'save_processed_data',
    'load_processed_data',
    'calculate_basic_drama_signals',
    'DRAMA_KEYWORDS',
    'POSITIVE_KEYWORDS',
]
