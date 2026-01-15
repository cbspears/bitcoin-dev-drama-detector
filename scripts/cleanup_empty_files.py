"""
Cleanup script to remove empty historical data files.

Removes daily score files and raw data files that contain no actual data
(all zeros or empty arrays).
"""

import os
import json
import argparse
from datetime import datetime


def is_empty_daily_score(filepath: str) -> bool:
    """Check if a daily score file has no real data (all zeros)."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Check if all scores are 0
        scores = [
            data.get('github', 0),
            data.get('bips', 0),
            data.get('mailing_list', 0),
            data.get('irc', 0),
            data.get('overall', 0)
        ]
        return all(s == 0 or s == 0.0 for s in scores)
    except (json.JSONDecodeError, FileNotFoundError):
        return True


def is_empty_raw_file(filepath: str, source: str) -> bool:
    """Check if a raw data file has no real data."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if source == 'github':
            prs = data.get('pull_requests', [])
            issues = data.get('issues', [])
            return len(prs) == 0 and len(issues) == 0

        elif source == 'bips':
            prs = data.get('pull_requests', [])
            issues = data.get('issues', [])
            return len(prs) == 0 and len(issues) == 0

        elif source == 'irc':
            logs = data.get('logs', [])
            total_msgs = sum(log.get('message_count', 0) for log in logs)
            return total_msgs == 0

        elif source == 'mailing_list':
            threads = data.get('threads', [])
            return len(threads) == 0

        return False
    except (json.JSONDecodeError, FileNotFoundError):
        return True


def cleanup_empty_files(data_dir: str, dry_run: bool = True) -> dict:
    """
    Find and optionally remove empty data files.

    Args:
        data_dir: Root data directory
        dry_run: If True, only report what would be deleted

    Returns:
        Summary of files found/deleted
    """
    summary = {
        'daily_scores': {'empty': 0, 'kept': 0, 'deleted': []},
        'github': {'empty': 0, 'kept': 0, 'deleted': []},
        'bips': {'empty': 0, 'kept': 0, 'deleted': []},
        'irc': {'empty': 0, 'kept': 0, 'deleted': []},
        'mailing_list': {'empty': 0, 'kept': 0, 'deleted': []}
    }

    # Check processed daily scores
    processed_dir = os.path.join(data_dir, 'processed')
    if os.path.exists(processed_dir):
        for filename in os.listdir(processed_dir):
            if filename.startswith('daily_scores_') and filename.endswith('.json'):
                filepath = os.path.join(processed_dir, filename)
                if is_empty_daily_score(filepath):
                    summary['daily_scores']['empty'] += 1
                    summary['daily_scores']['deleted'].append(filename)
                    if not dry_run:
                        os.remove(filepath)
                else:
                    summary['daily_scores']['kept'] += 1

    # Check raw data directories
    for source in ['github', 'bips', 'irc', 'mailing_list']:
        source_dir = os.path.join(data_dir, 'raw', source)
        if os.path.exists(source_dir):
            for filename in os.listdir(source_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(source_dir, filename)
                    if is_empty_raw_file(filepath, source):
                        summary[source]['empty'] += 1
                        summary[source]['deleted'].append(filename)
                        if not dry_run:
                            os.remove(filepath)
                    else:
                        summary[source]['kept'] += 1

    return summary


def main():
    parser = argparse.ArgumentParser(description='Clean up empty historical data files')
    parser.add_argument('--data-dir', type=str, default='data',
                        help='Path to data directory')
    parser.add_argument('--execute', action='store_true',
                        help='Actually delete files (default is dry-run)')

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"Empty File Cleanup")
    print(f"Data directory: {args.data_dir}")
    print(f"Mode: {'EXECUTE (will delete files)' if args.execute else 'DRY RUN (no changes)'}")
    print(f"{'='*60}\n")

    summary = cleanup_empty_files(args.data_dir, dry_run=not args.execute)

    print("\nSummary:")
    print("-" * 40)

    total_empty = 0
    total_kept = 0

    for category, stats in summary.items():
        empty = stats['empty']
        kept = stats['kept']
        total_empty += empty
        total_kept += kept

        if empty > 0 or kept > 0:
            print(f"\n{category}:")
            print(f"  Empty (to delete): {empty}")
            print(f"  With data (kept):  {kept}")

            if empty > 0 and empty <= 10:
                print(f"  Files: {', '.join(stats['deleted'][:10])}")
            elif empty > 10:
                print(f"  Files: {', '.join(stats['deleted'][:5])}... and {empty - 5} more")

    print(f"\n{'='*40}")
    print(f"Total empty files: {total_empty}")
    print(f"Total files with data: {total_kept}")

    if not args.execute and total_empty > 0:
        print(f"\n[!] Run with --execute to actually delete the empty files")
    elif args.execute and total_empty > 0:
        print(f"\nDeleted {total_empty} empty files")
    else:
        print(f"\nNo empty files to clean up")


if __name__ == '__main__':
    main()
