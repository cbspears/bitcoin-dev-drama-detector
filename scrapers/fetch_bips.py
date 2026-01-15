"""
BIPs Repository Scraper for Bitcoin Dev Drama Detector

Fetches recent activity from the bitcoin/bips repository:
- Pull requests (new, updated, comments)
- Issues (new, updated, comments)
- Review comments

BIPs (Bitcoin Improvement Proposals) are where protocol-level discussions happen.
This is often a major source of drama as it involves consensus changes.

Uses GitHub REST API with pagination support.
"""

import os
import sys
import time
import requests
from datetime import datetime, timezone
from typing import Generator, Optional, List, Dict, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.utils import (
    logger,
    get_date_range,
    save_raw_data,
    format_iso_date,
    calculate_basic_drama_signals
)


class BIPsScraper:
    """Scraper for bitcoin/bips GitHub repository."""

    BASE_URL = "https://api.github.com"
    REPO = "bitcoin/bips"

    def __init__(self, token: str = None):
        """
        Initialize the BIPs scraper.

        Args:
            token: GitHub personal access token (optional but recommended)
        """
        self.token = token or os.getenv('GITHUB_TOKEN')
        self.session = requests.Session()

        # Set headers
        self.session.headers.update({
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'BitcoinDramaDetector/1.0'
        })

        if self.token:
            self.session.headers['Authorization'] = f'token {self.token}'
            logger.info("GitHub token configured for BIPs scraper")
        else:
            logger.warning("No GitHub token - rate limits will be stricter (60 req/hr)")

    def _request(self, endpoint: str, params: dict = None) -> Union[dict, list]:
        """
        Make a request to the GitHub API with rate limit handling.

        Args:
            endpoint: API endpoint (relative to BASE_URL)
            params: Query parameters

        Returns:
            JSON response data
        """
        url = f"{self.BASE_URL}{endpoint}"

        response = self.session.get(url, params=params)

        # Check rate limits
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))

        if remaining < 10:
            logger.warning(f"GitHub rate limit low: {remaining} remaining")

        if response.status_code == 403 and 'rate limit' in response.text.lower():
            wait_time = max(reset_time - time.time(), 60)
            logger.error(f"Rate limited. Waiting {wait_time:.0f}s")
            time.sleep(wait_time)
            return self._request(endpoint, params)

        response.raise_for_status()
        return response.json()

    def _paginate(self, endpoint: str, params: dict = None, max_pages: int = 10) -> Generator[dict, None, None]:
        """
        Paginate through GitHub API results.

        Args:
            endpoint: API endpoint
            params: Query parameters
            max_pages: Maximum number of pages to fetch

        Yields:
            Individual items from paginated results
        """
        params = params or {}
        params['per_page'] = 100
        page = 1

        while page <= max_pages:
            params['page'] = page
            results = self._request(endpoint, params)

            if not results:
                break

            for item in results:
                yield item

            if len(results) < 100:
                break

            page += 1

    def fetch_pull_requests(self, since: datetime) -> List[dict]:
        """
        Fetch pull requests updated since the given date.

        Args:
            since: Fetch PRs updated after this datetime

        Returns:
            List of PR data dictionaries
        """
        logger.info(f"Fetching BIPs PRs updated since {since}")

        prs = []
        endpoint = f"/repos/{self.REPO}/pulls"
        params = {
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc'
        }

        for pr in self._paginate(endpoint, params):
            updated_at = datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00'))

            if updated_at < since:
                break

            pr_data = {
                'id': pr['id'],
                'number': pr['number'],
                'title': pr['title'],
                'body': pr.get('body') or '',
                'state': pr['state'],
                'user': pr['user']['login'],
                'created_at': pr['created_at'],
                'updated_at': pr['updated_at'],
                'merged_at': pr.get('merged_at'),
                'comments': pr.get('comments', 0),
                'review_comments': pr.get('review_comments', 0),
                'url': pr['html_url'],
                'labels': [l['name'] for l in pr.get('labels', [])],
            }

            # Fetch comments if there are any
            if pr_data['comments'] > 0 or pr_data['review_comments'] > 0:
                pr_data['comment_data'] = self._fetch_pr_comments(pr['number'], since)

            # Calculate basic drama signals
            full_text = f"{pr_data['title']} {pr_data['body']}"
            pr_data['drama_signals'] = calculate_basic_drama_signals(full_text)

            prs.append(pr_data)
            logger.debug(f"Fetched BIP PR #{pr['number']}: {pr['title'][:50]}")

        logger.info(f"Fetched {len(prs)} BIPs pull requests")
        return prs

    def _fetch_pr_comments(self, pr_number: int, since: datetime) -> List[dict]:
        """
        Fetch comments on a specific PR.

        Args:
            pr_number: The PR number
            since: Only fetch comments after this date

        Returns:
            List of comment dictionaries
        """
        comments = []

        # Issue comments (general discussion)
        endpoint = f"/repos/{self.REPO}/issues/{pr_number}/comments"
        for comment in self._paginate(endpoint, max_pages=5):
            created_at = datetime.fromisoformat(comment['created_at'].replace('Z', '+00:00'))
            if created_at >= since:
                comments.append({
                    'id': comment['id'],
                    'type': 'issue_comment',
                    'user': comment['user']['login'],
                    'body': comment['body'],
                    'created_at': comment['created_at'],
                    'drama_signals': calculate_basic_drama_signals(comment['body'])
                })

        # Review comments (inline code comments)
        endpoint = f"/repos/{self.REPO}/pulls/{pr_number}/comments"
        for comment in self._paginate(endpoint, max_pages=5):
            created_at = datetime.fromisoformat(comment['created_at'].replace('Z', '+00:00'))
            if created_at >= since:
                comments.append({
                    'id': comment['id'],
                    'type': 'review_comment',
                    'user': comment['user']['login'],
                    'body': comment['body'],
                    'created_at': comment['created_at'],
                    'path': comment.get('path'),
                    'drama_signals': calculate_basic_drama_signals(comment['body'])
                })

        return comments

    def fetch_issues(self, since: datetime) -> List[dict]:
        """
        Fetch issues updated since the given date.

        Args:
            since: Fetch issues updated after this datetime

        Returns:
            List of issue data dictionaries
        """
        logger.info(f"Fetching BIPs issues updated since {since}")

        issues = []
        endpoint = f"/repos/{self.REPO}/issues"
        params = {
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc',
            'since': format_iso_date(since)
        }

        for issue in self._paginate(endpoint, params):
            # Skip pull requests (they appear in issues endpoint too)
            if 'pull_request' in issue:
                continue

            issue_data = {
                'id': issue['id'],
                'number': issue['number'],
                'title': issue['title'],
                'body': issue.get('body') or '',
                'state': issue['state'],
                'user': issue['user']['login'],
                'created_at': issue['created_at'],
                'updated_at': issue['updated_at'],
                'closed_at': issue.get('closed_at'),
                'comments': issue.get('comments', 0),
                'url': issue['html_url'],
                'labels': [l['name'] for l in issue.get('labels', [])],
            }

            # Fetch comments if there are any
            if issue_data['comments'] > 0:
                issue_data['comment_data'] = self._fetch_issue_comments(issue['number'], since)

            # Calculate basic drama signals
            full_text = f"{issue_data['title']} {issue_data['body']}"
            issue_data['drama_signals'] = calculate_basic_drama_signals(full_text)

            issues.append(issue_data)
            logger.debug(f"Fetched BIP issue #{issue['number']}: {issue['title'][:50]}")

        logger.info(f"Fetched {len(issues)} BIPs issues")
        return issues

    def _fetch_issue_comments(self, issue_number: int, since: datetime) -> List[dict]:
        """
        Fetch comments on a specific issue.

        Args:
            issue_number: The issue number
            since: Only fetch comments after this date

        Returns:
            List of comment dictionaries
        """
        comments = []
        endpoint = f"/repos/{self.REPO}/issues/{issue_number}/comments"
        params = {'since': format_iso_date(since)}

        for comment in self._paginate(endpoint, params, max_pages=5):
            comments.append({
                'id': comment['id'],
                'user': comment['user']['login'],
                'body': comment['body'],
                'created_at': comment['created_at'],
                'drama_signals': calculate_basic_drama_signals(comment['body'])
            })

        return comments

    def fetch_all(self, days_back: int = 1) -> dict:
        """
        Fetch all BIPs GitHub data for the specified time period.

        Args:
            days_back: Number of days to look back

        Returns:
            Dictionary containing all fetched data
        """
        since, until = get_date_range(days_back)

        logger.info(f"Fetching BIPs data from {since} to {until}")

        data = {
            'source': 'bips',
            'repo': self.REPO,
            'fetched_at': datetime.now(timezone.utc).isoformat(),
            'date_range': {
                'since': since.isoformat(),
                'until': until.isoformat()
            },
            'pull_requests': self.fetch_pull_requests(since),
            'issues': self.fetch_issues(since),
        }

        # Calculate summary stats
        data['summary'] = {
            'total_prs': len(data['pull_requests']),
            'total_issues': len(data['issues']),
            'total_comments': sum(
                len(pr.get('comment_data', [])) for pr in data['pull_requests']
            ) + sum(
                len(issue.get('comment_data', [])) for issue in data['issues']
            ),
            'unique_participants': len(set(
                [pr['user'] for pr in data['pull_requests']] +
                [issue['user'] for issue in data['issues']] +
                [c['user'] for pr in data['pull_requests'] for c in pr.get('comment_data', [])] +
                [c['user'] for issue in data['issues'] for c in issue.get('comment_data', [])]
            ))
        }

        logger.info(f"BIPs fetch complete: {data['summary']}")
        return data


def main():
    """Main entry point for BIPs scraper."""
    import argparse

    parser = argparse.ArgumentParser(description='Fetch BIPs repository data for Bitcoin Dev Drama Detector')
    parser.add_argument('--days', type=int, default=1, help='Number of days to look back')
    parser.add_argument('--token', type=str, help='GitHub token (or set GITHUB_TOKEN env var)')
    args = parser.parse_args()

    scraper = BIPsScraper(token=args.token)
    data = scraper.fetch_all(days_back=args.days)

    # Save the data
    date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    save_raw_data(data, 'bips', date_str)

    print(f"\n✅ BIPs scrape complete!")
    print(f"   PRs: {data['summary']['total_prs']}")
    print(f"   Issues: {data['summary']['total_issues']}")
    print(f"   Comments: {data['summary']['total_comments']}")
    print(f"   Participants: {data['summary']['unique_participants']}")


if __name__ == '__main__':
    main()
