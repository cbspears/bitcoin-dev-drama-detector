"""
Re-analyze historical raw data to generate daily scores.

This script reads all raw data files and runs the multi-dimensional
analyzer to generate proper daily scores.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analyzer.multi_dimensional_analyzer import MultiDimensionalAnalyzer
from scrapers.utils import logger


def load_raw_data(data_dir: str, source: str, date_str: str) -> dict:
    """Load raw data file for a source and date."""
    filepath = os.path.join(data_dir, 'raw', source, f'{date_str}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def analyze_github_data(data: dict, analyzer: MultiDimensionalAnalyzer) -> float:
    """Analyze GitHub raw data and return drama score."""
    if not data:
        return 0.0

    scores = []

    # Analyze PRs
    for pr in data.get('pull_requests', []):
        title = pr.get('title', '')
        body = pr.get('body', '') or ''
        text = f"{title} {body}"

        if text.strip():
            result = analyzer.analyze(text)
            scores.append(result.drama_score)

        # Analyze comments (handle both list and count formats)
        comments = pr.get('comments', [])
        if isinstance(comments, list):
            for comment in comments:
                comment_body = comment.get('body', '') or ''
                if comment_body.strip():
                    result = analyzer.analyze(comment_body)
                    scores.append(result.drama_score)

    # Analyze issues
    for issue in data.get('issues', []):
        title = issue.get('title', '')
        body = issue.get('body', '') or ''
        text = f"{title} {body}"

        if text.strip():
            result = analyzer.analyze(text)
            scores.append(result.drama_score)

        comments = issue.get('comments', [])
        if isinstance(comments, list):
            for comment in comments:
                comment_body = comment.get('body', '') or ''
                if comment_body.strip():
                    result = analyzer.analyze(comment_body)
                    scores.append(result.drama_score)

    if scores:
        return sum(scores) / len(scores)
    return 0.0


def analyze_irc_data(data: dict, analyzer: MultiDimensionalAnalyzer) -> float:
    """Analyze IRC raw data and return drama score."""
    if not data:
        return 0.0

    scores = []

    for log in data.get('logs', []):
        for msg in log.get('messages', []):
            content = msg.get('content', '')
            if content.strip() and len(content) > 10:
                result = analyzer.analyze(content)
                scores.append(result.drama_score)

    if scores:
        return sum(scores) / len(scores)
    return 0.0


def analyze_mailing_list_data(data: dict, analyzer: MultiDimensionalAnalyzer) -> float:
    """Analyze mailing list raw data and return drama score."""
    if not data:
        return 0.0

    scores = []

    for thread in data.get('threads', []):
        for msg in thread.get('messages', []):
            title = msg.get('title', '')
            body = msg.get('body', '')
            text = f"{title} {body}"

            if text.strip() and len(text) > 10:
                result = analyzer.analyze(text)
                scores.append(result.drama_score)

    if scores:
        return sum(scores) / len(scores)
    return 0.0


def save_daily_scores(data_dir: str, date_str: str, scores: dict):
    """Save daily scores to processed directory."""
    filepath = os.path.join(data_dir, 'processed', f'daily_scores_{date_str}.json')
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(scores, f, indent=2)


def reanalyze_date(data_dir: str, date_str: str, analyzer: MultiDimensionalAnalyzer) -> dict:
    """Re-analyze all raw data for a specific date."""
    # Load raw data
    github_data = load_raw_data(data_dir, 'github', date_str)
    bips_data = load_raw_data(data_dir, 'bips', date_str)
    irc_data = load_raw_data(data_dir, 'irc', date_str)
    ml_data = load_raw_data(data_dir, 'mailing_list', date_str)

    # Analyze each source
    github_score = analyze_github_data(github_data, analyzer)
    bips_score = analyze_github_data(bips_data, analyzer)  # Same format as GitHub
    irc_score = analyze_irc_data(irc_data, analyzer)
    ml_score = analyze_mailing_list_data(ml_data, analyzer)

    # Calculate overall (weighted average of non-zero scores)
    source_scores = [
        ('github', github_score, 0.35),
        ('bips', bips_score, 0.25),
        ('irc', irc_score, 0.20),
        ('mailing_list', ml_score, 0.20),
    ]

    total_weight = sum(w for _, s, w in source_scores if s > 0)
    if total_weight > 0:
        overall = sum(s * w for _, s, w in source_scores if s > 0) / total_weight
    else:
        overall = 0.0

    return {
        'date': date_str,
        'github': round(github_score, 1),
        'bips': round(bips_score, 1),
        'mailing_list': round(ml_score, 1),
        'irc': round(irc_score, 1),
        'overall': round(overall, 1)
    }


def main():
    parser = argparse.ArgumentParser(description='Re-analyze historical raw data')
    parser.add_argument('--data-dir', type=str, default='data',
                        help='Path to data directory')
    parser.add_argument('--start', type=str, required=True,
                        help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, required=True,
                        help='End date (YYYY-MM-DD)')
    parser.add_argument('--force', action='store_true',
                        help='Re-analyze even if score file exists with non-zero data')

    args = parser.parse_args()

    start_date = datetime.strptime(args.start, '%Y-%m-%d')
    end_date = datetime.strptime(args.end, '%Y-%m-%d')

    print(f"\n{'='*60}")
    print(f"Re-analyzing Historical Data")
    print(f"Date range: {args.start} to {args.end}")
    print(f"Total days: {(end_date - start_date).days + 1}")
    print(f"Force re-analyze: {args.force}")
    print(f"{'='*60}\n")

    # Initialize analyzer
    print("Initializing multi-dimensional analyzer...")
    analyzer = MultiDimensionalAnalyzer()

    current_date = start_date
    total_days = (end_date - start_date).days + 1
    processed = 0
    updated = 0

    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        processed += 1

        # Check if we should skip
        score_path = os.path.join(args.data_dir, 'processed', f'daily_scores_{date_str}.json')
        if os.path.exists(score_path) and not args.force:
            with open(score_path, 'r') as f:
                existing = json.load(f)
                if existing.get('overall', 0) > 0:
                    print(f"[{processed}/{total_days}] {date_str}: Already has scores, skipping")
                    current_date += timedelta(days=1)
                    continue

        print(f"[{processed}/{total_days}] Analyzing {date_str}...", end=' ')

        scores = reanalyze_date(args.data_dir, date_str, analyzer)
        save_daily_scores(args.data_dir, date_str, scores)

        print(f"github={scores['github']}, irc={scores['irc']}, ml={scores['mailing_list']}, overall={scores['overall']}")
        updated += 1

        current_date += timedelta(days=1)

    print(f"\nComplete! Processed {processed} days, updated {updated} score files.")


if __name__ == '__main__':
    main()
