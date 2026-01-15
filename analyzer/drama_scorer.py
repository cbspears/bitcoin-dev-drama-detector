"""
Drama Scorer - Uses Claude API to analyze Bitcoin dev discussions for controversy signals.

This module takes raw scraped data and produces drama scores, identifying:
- Overall drama levels (0-10 scale)
- Hot topics and their heat scores
- Contentious threads
- Key participants in heated discussions
"""

import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import defaultdict, Counter

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from anthropic import Anthropic
from dotenv import load_dotenv

from scrapers.utils import (
    logger,
    load_raw_data,
    save_processed_data,
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR
)

# Load environment variables
load_dotenv()


class DramaScorer:
    """Analyzes Bitcoin dev discussions for drama/controversy signals."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the drama scorer.

        Args:
            api_key: Anthropic API key (or uses ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

    def _create_drama_analysis_prompt(self, content: str, context: str = "GitHub PR") -> str:
        """
        Create a prompt for Claude to analyze drama levels.

        Args:
            content: The text content to analyze
            context: Context about the content (e.g., "GitHub PR", "IRC discussion")

        Returns:
            Formatted prompt for Claude
        """
        return f"""You are analyzing Bitcoin developer discussions for signs of controversy, debate intensity, and consensus issues.

Context: {context}

Content to analyze:
{content}

Please analyze this content and provide:

1. **Drama Score (0-10)**: How contentious/heated is this discussion?
   - 0-2: Calm, constructive, consensus
   - 3-4: Minor disagreement, mostly constructive
   - 5-6: Active debate, some friction
   - 7-8: Heated discussion, significant disagreement
   - 9-10: Highly contentious, strong opposition

2. **Key Signals**: What specific indicators suggest drama?
   - Strong disagreement phrases (NACK, "fundamentally wrong", etc.)
   - Personal/political undertones
   - References to past controversies
   - Activation/consensus concerns

3. **Main Topics**: What are the core topics being discussed?

4. **Stance Summary**: What are the main positions/viewpoints?

Respond in JSON format:
{{
  "drama_score": <number 0-10>,
  "signals": [<list of specific drama signals found>],
  "topics": [<list of main topics>],
  "stance_summary": "<brief summary of positions>",
  "key_phrases": [<notable quotes or phrases>]
}}"""

    def analyze_text(self, content: str, context: str = "discussion") -> Dict:
        """
        Use Claude API to analyze a piece of text for drama signals.

        Args:
            content: Text to analyze
            context: Context description

        Returns:
            Analysis results dict with drama_score and signals
        """
        # Truncate very long content to stay within limits
        max_chars = 8000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated...]"

        prompt = self._create_drama_analysis_prompt(content, context)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract JSON from response
            response_text = response.content[0].text

            # Try to parse JSON (Claude might wrap it in markdown code blocks)
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            result = json.loads(response_text)
            return result

        except Exception as e:
            logger.error(f"Error analyzing with Claude API: {e}")
            # Return default low-drama result on error
            return {
                "drama_score": 2.0,
                "signals": [],
                "topics": ["unknown"],
                "stance_summary": "Unable to analyze",
                "key_phrases": []
            }

    def analyze_github_pr(self, pr: Dict) -> Dict:
        """
        Analyze a GitHub PR for drama signals.

        Args:
            pr: PR data dict from scraper

        Returns:
            Enhanced PR dict with drama analysis
        """
        # Combine PR title, body, and comments into analysis text
        content_parts = [
            f"PR #{pr['number']}: {pr['title']}",
            pr.get('body', '')[:1000]  # First 1000 chars of body
        ]

        # Add comments if available
        if pr.get('comment_data'):
            comments = pr['comment_data'][:10]  # First 10 comments
            for comment in comments:
                content_parts.append(f"Comment by {comment['user']}: {comment['body'][:300]}")

        full_content = "\n\n".join(content_parts)

        analysis = self.analyze_text(
            full_content,
            context=f"GitHub PR #{pr['number']}"
        )

        return {
            **pr,
            'drama_analysis': analysis,
            'drama_score': analysis['drama_score']
        }

    def analyze_github_issue(self, issue: Dict) -> Dict:
        """
        Analyze a GitHub issue for drama signals.

        Args:
            issue: Issue data dict from scraper

        Returns:
            Enhanced issue dict with drama analysis
        """
        content_parts = [
            f"Issue #{issue['number']}: {issue['title']}",
            issue.get('body', '')[:1000]
        ]

        if issue.get('comment_data'):
            comments = issue['comment_data'][:10]
            for comment in comments:
                content_parts.append(f"Comment by {comment['user']}: {comment['body'][:300]}")

        full_content = "\n\n".join(content_parts)

        analysis = self.analyze_text(
            full_content,
            context=f"GitHub Issue #{issue['number']}"
        )

        return {
            **issue,
            'drama_analysis': analysis,
            'drama_score': analysis['drama_score']
        }

    def calculate_daily_scores(
        self,
        github_data: Optional[Dict] = None,
        bips_data: Optional[Dict] = None,
        irc_data: Optional[Dict] = None,
        mailing_list_data: Optional[Dict] = None
    ) -> Dict:
        """
        Calculate overall drama scores for each source.

        Args:
            github_data: GitHub data dict from scraper
            bips_data: BIPs repository data dict from scraper
            irc_data: IRC data dict from scraper
            mailing_list_data: Mailing list data dict from scraper

        Returns:
            Daily scores dict for dashboard
        """
        scores = {
            'github': 0.0,
            'bips': 0.0,
            'mailing_list': 0.0,
            'irc': 0.0,
            'overall': 0.0
        }

        # Calculate GitHub score if data available
        if github_data:
            all_scores = []

            # Analyze PRs
            for pr in github_data.get('pull_requests', [])[:20]:  # Sample first 20
                analyzed = self.analyze_github_pr(pr)
                all_scores.append(analyzed['drama_score'])

            # Analyze issues
            for issue in github_data.get('issues', [])[:10]:  # Sample first 10
                analyzed = self.analyze_github_issue(issue)
                all_scores.append(analyzed['drama_score'])

            if all_scores:
                scores['github'] = round(sum(all_scores) / len(all_scores), 1)

        # Calculate BIPs score if data available
        if bips_data:
            all_scores = []

            # Analyze BIP PRs
            for pr in bips_data.get('pull_requests', [])[:20]:  # Sample first 20
                analyzed = self.analyze_github_pr(pr)
                all_scores.append(analyzed['drama_score'])

            # Analyze BIP issues
            for issue in bips_data.get('issues', [])[:10]:  # Sample first 10
                analyzed = self.analyze_github_issue(issue)
                all_scores.append(analyzed['drama_score'])

            if all_scores:
                scores['bips'] = round(sum(all_scores) / len(all_scores), 1)

        # Calculate IRC score if data available
        if irc_data:
            all_scores = []
            # Sample IRC threads
            for log in irc_data.get('logs', []):
                for thread in log.get('threads', [])[:5]:  # Sample 5 threads per day
                    # Use basic drama signals for quick scoring
                    signals = thread.get('drama_signals', {})
                    score = min(10, signals.get('drama_keywords', 0) * 2)
                    all_scores.append(score)

            if all_scores:
                scores['irc'] = round(sum(all_scores) / len(all_scores), 1)

        # Calculate mailing list score if data available
        if mailing_list_data:
            all_scores = []
            # Sample mailing list threads
            for thread in mailing_list_data.get('threads', [])[:10]:  # Sample 10 threads
                # Use basic drama signals for quick scoring
                signals = thread.get('drama_signals', {})
                score = min(10, signals.get('drama_keywords', 0) * 2)
                all_scores.append(score)

            if all_scores:
                scores['mailing_list'] = round(sum(all_scores) / len(all_scores), 1)

        # Overall is average of available sources
        available_scores = [s for s in [scores['github'], scores['bips'], scores['mailing_list'], scores['irc']] if s > 0]
        if available_scores:
            scores['overall'] = round(sum(available_scores) / len(available_scores), 1)

        return scores

    def extract_hot_topics(
        self,
        github_data: Optional[Dict] = None,
        bips_data: Optional[Dict] = None,
        irc_data: Optional[Dict] = None,
        mailing_list_data: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Extract hot topics from discussions.

        Args:
            github_data: GitHub data dict
            bips_data: BIPs repository data dict
            irc_data: IRC data dict
            mailing_list_data: Mailing list data dict

        Returns:
            List of hot topics with heat scores
        """
        topics_counter = Counter()
        topic_drama_scores = defaultdict(list)
        topic_sources = defaultdict(set)

        if github_data:
            # Analyze a sample of PRs and issues
            items = (
                github_data.get('pull_requests', [])[:30] +
                github_data.get('issues', [])[:20]
            )

            for item in items:
                # Quick analysis or use existing basic drama signals
                content = f"{item['title']} {item.get('body', '')}"
                drama_score = item.get('drama_signals', {}).get('drama_keywords', 0)

                # Extract topics from title (simple approach)
                # Look for BIP numbers, feature names, etc.
                topics = self._extract_topics_from_text(item['title'])

                for topic in topics:
                    topics_counter[topic] += 1
                    topic_drama_scores[topic].append(drama_score)
                    topic_sources[topic].add('github')

        if bips_data:
            # Analyze BIPs PRs and issues
            items = (
                bips_data.get('pull_requests', [])[:30] +
                bips_data.get('issues', [])[:20]
            )

            for item in items:
                content = f"{item['title']} {item.get('body', '')}"
                drama_score = item.get('drama_signals', {}).get('drama_keywords', 0)

                topics = self._extract_topics_from_text(item['title'])

                for topic in topics:
                    topics_counter[topic] += 1
                    topic_drama_scores[topic].append(drama_score)
                    topic_sources[topic].add('bips')

        # Build hot topics list
        hot_topics = []
        for topic, count in topics_counter.most_common(10):
            scores = topic_drama_scores[topic]
            avg_score = sum(scores) / len(scores) if scores else 0

            # Determine primary source (the one with most mentions)
            sources = list(topic_sources[topic])
            primary_source = sources[0] if sources else 'github'

            hot_topics.append({
                'topic': topic,
                'heat_score': min(10, round(avg_score * 2, 1)),  # Scale up for visibility
                'trend': 'stable',  # Would need historical data for real trends
                'mentions_24h': count,
                'primary_source': primary_source
            })

        return hot_topics

    def _extract_topics_from_text(self, text: str) -> List[str]:
        """
        Extract topics/keywords from text.

        Args:
            text: Text to analyze

        Returns:
            List of identified topics
        """
        text_lower = text.lower()
        topics = []

        # Common Bitcoin dev topics
        topic_keywords = {
            'taproot': ['taproot', 'bip340', 'bip341', 'bip342'],
            'mempool': ['mempool', 'rbf', 'package relay', 'cluster mempool'],
            'wallet': ['wallet', 'descriptor', 'psbt'],
            'consensus': ['consensus', 'soft fork', 'hard fork', 'activation'],
            'p2p': ['p2p', 'peer', 'network', 'connection'],
            'testing': ['test', 'fuzzing', 'ci', 'coverage'],
            'gui': ['gui', 'qt', 'interface'],
            'rpc': ['rpc', 'rest', 'api'],
            'validation': ['validation', 'verify', 'check'],
            'mining': ['mining', 'block template', 'getblocktemplate'],
        }

        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)

        # Look for BIP/PR numbers
        if 'bip' in text_lower or '#' in text:
            if not any(t.startswith('BIP') for t in topics):
                topics.append('BIP Discussion')

        return topics if topics else ['general']

    def identify_spicy_threads(
        self,
        github_data: Optional[Dict] = None,
        bips_data: Optional[Dict] = None,
        irc_data: Optional[Dict] = None,
        mailing_list_data: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Identify the most contentious threads/discussions.

        Args:
            github_data: GitHub data dict
            bips_data: BIPs repository data dict
            irc_data: IRC data dict
            mailing_list_data: Mailing list data dict
            limit: Number of threads to return

        Returns:
            List of spicy threads with drama scores
        """
        threads = []

        # Process GitHub data
        if github_data:
            # Combine PRs and issues
            items = github_data.get('pull_requests', []) + github_data.get('issues', [])

            # Score each item based on basic signals
            for item in items:
                signals = item.get('drama_signals', {})

                # Calculate a quick drama score
                drama_score = (
                    signals.get('drama_keywords', 0) * 2.0 +
                    signals.get('has_nack', False) * 3.0 -
                    signals.get('positive_keywords', 0) * 0.5
                )

                comment_count = item.get('comments', 0) + item.get('review_comments', 0)

                # Boost score for high activity
                if comment_count > 20:
                    drama_score += 2.0
                elif comment_count > 10:
                    drama_score += 1.0

                # Normalize to 0-10
                drama_score = max(0, min(10, drama_score))

                if drama_score >= 4.0:  # Only include moderately spicy threads
                    threads.append({
                        'id': f"gh-{item['number']}",
                        'title': item['title'],
                        'source': 'github',
                        'drama_score': round(drama_score, 1),
                        'date': item['created_at'][:10],
                        'participants': [item['user']],
                        'nack_count': 1 if signals.get('has_nack') else 0,
                        'ack_count': 1 if signals.get('has_ack') else 0,
                        'key_phrases': [],  # Would need full analysis
                        'url': item['url']
                    })

        # Process BIPs data
        if bips_data:
            # Combine PRs and issues
            items = bips_data.get('pull_requests', []) + bips_data.get('issues', [])

            # Score each item based on basic signals
            for item in items:
                signals = item.get('drama_signals', {})

                # Calculate a quick drama score
                drama_score = (
                    signals.get('drama_keywords', 0) * 2.0 +
                    signals.get('has_nack', False) * 3.0 -
                    signals.get('positive_keywords', 0) * 0.5
                )

                comment_count = item.get('comments', 0) + item.get('review_comments', 0)

                # Boost score for high activity
                if comment_count > 20:
                    drama_score += 2.0
                elif comment_count > 10:
                    drama_score += 1.0

                # Normalize to 0-10
                drama_score = max(0, min(10, drama_score))

                if drama_score >= 4.0:  # Only include moderately spicy threads
                    threads.append({
                        'id': f"bip-{item['number']}",
                        'title': item['title'],
                        'source': 'bips',
                        'drama_score': round(drama_score, 1),
                        'date': item['created_at'][:10],
                        'participants': [item['user']],
                        'nack_count': 1 if signals.get('has_nack') else 0,
                        'ack_count': 1 if signals.get('has_ack') else 0,
                        'key_phrases': [],  # Would need full analysis
                        'url': item['url']
                    })

        # Sort by drama score and return top threads
        threads.sort(key=lambda x: x['drama_score'], reverse=True)
        return threads[:limit]

    def identify_key_participants(
        self,
        github_data: Optional[Dict] = None,
        bips_data: Optional[Dict] = None,
        irc_data: Optional[Dict] = None,
        mailing_list_data: Optional[Dict] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Identify the most active participants in discussions.

        Args:
            github_data: GitHub data dict
            bips_data: BIPs repository data dict
            irc_data: IRC data dict
            mailing_list_data: Mailing list data dict
            limit: Number of participants to return

        Returns:
            List of key participants with activity metrics
        """
        participant_stats = defaultdict(lambda: {
            'messages': 0,
            'drama_contributions': []
        })

        if github_data:
            # Count PR/issue authors
            for pr in github_data.get('pull_requests', []):
                user = pr['user']
                signals = pr.get('drama_signals', {})
                drama_level = signals.get('drama_keywords', 0)

                participant_stats[user]['messages'] += 1
                participant_stats[user]['drama_contributions'].append(drama_level)

            for issue in github_data.get('issues', []):
                user = issue['user']
                signals = issue.get('drama_signals', {})
                drama_level = signals.get('drama_keywords', 0)

                participant_stats[user]['messages'] += 1
                participant_stats[user]['drama_contributions'].append(drama_level)

        if bips_data:
            # Count BIP PR/issue authors
            for pr in bips_data.get('pull_requests', []):
                user = pr['user']
                signals = pr.get('drama_signals', {})
                drama_level = signals.get('drama_keywords', 0)

                participant_stats[user]['messages'] += 1
                participant_stats[user]['drama_contributions'].append(drama_level)

            for issue in bips_data.get('issues', []):
                user = issue['user']
                signals = issue.get('drama_signals', {})
                drama_level = signals.get('drama_keywords', 0)

                participant_stats[user]['messages'] += 1
                participant_stats[user]['drama_contributions'].append(drama_level)

        # Build participant list
        participants = []
        for user, stats in participant_stats.items():
            drama_scores = stats['drama_contributions']
            avg_drama = sum(drama_scores) / len(drama_scores) if drama_scores else 0

            participants.append({
                'name': user,
                'handle': user,
                'messages': stats['messages'],
                'avg_drama_contribution': round(avg_drama, 1),
                'stance_summary': 'Active contributor',
                'primary_topics': ['general']
            })

        # Sort by activity level
        participants.sort(key=lambda x: x['messages'], reverse=True)
        return participants[:limit]

    def process_all_data(self, date_str: Optional[str] = None) -> Dict:
        """
        Process all available raw data and generate dashboard outputs.

        Args:
            date_str: Date string (YYYY-MM-DD) to process, defaults to latest

        Returns:
            Summary of processed data
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        logger.info(f"Processing data for {date_str}")

        # Load raw data from all sources
        github_data = load_raw_data('github', date_str)
        bips_data = load_raw_data('bips', date_str)
        irc_data = load_raw_data('irc', date_str)
        mailing_list_data = load_raw_data('mailing_list', date_str)

        if not github_data:
            logger.warning(f"No GitHub data found for {date_str}")
            github_data = None

        if not bips_data:
            logger.warning(f"No BIPs data found for {date_str}")
            bips_data = None

        if not irc_data:
            logger.warning(f"No IRC data found for {date_str}")
            irc_data = None

        if not mailing_list_data:
            logger.warning(f"No mailing list data found for {date_str}")
            mailing_list_data = None

        # Generate outputs
        logger.info("Calculating daily scores...")
        daily_scores = {
            'date': date_str,
            **self.calculate_daily_scores(github_data, bips_data, irc_data, mailing_list_data)
        }

        logger.info("Extracting hot topics...")
        hot_topics = self.extract_hot_topics(github_data, bips_data, irc_data, mailing_list_data)

        logger.info("Identifying spicy threads...")
        spicy_threads = self.identify_spicy_threads(github_data, bips_data, irc_data, mailing_list_data)

        logger.info("Identifying key participants...")
        key_participants = self.identify_key_participants(github_data, bips_data, irc_data, mailing_list_data)

        # Save processed data
        save_processed_data(daily_scores, f'daily_scores_{date_str}.json')
        save_processed_data({'hot_topics': hot_topics}, 'hot_topics.json')
        save_processed_data({'spicy_threads': spicy_threads}, 'spicy_threads.json')
        save_processed_data({'key_participants': key_participants}, 'key_participants.json')

        summary = {
            'date': date_str,
            'daily_scores': daily_scores,
            'hot_topics_count': len(hot_topics),
            'spicy_threads_count': len(spicy_threads),
            'key_participants_count': len(key_participants)
        }

        logger.info(f"Processing complete: {summary}")
        return summary


def main():
    """Main entry point for drama scorer."""
    import argparse

    parser = argparse.ArgumentParser(description='Analyze Bitcoin dev discussions for drama signals')
    parser.add_argument('--date', type=str, help='Date to process (YYYY-MM-DD), defaults to latest')
    parser.add_argument('--api-key', type=str, help='Anthropic API key (or set ANTHROPIC_API_KEY env var)')
    args = parser.parse_args()

    try:
        scorer = DramaScorer(api_key=args.api_key)
        result = scorer.process_all_data(date_str=args.date)

        print(f"\n✅ Drama analysis complete!")
        print(f"   Date: {result['date']}")
        print(f"   Overall Drama Score: {result['daily_scores']['overall']}")
        print(f"   GitHub Score: {result['daily_scores']['github']}")
        print(f"   Hot Topics: {result['hot_topics_count']}")
        print(f"   Spicy Threads: {result['spicy_threads_count']}")
        print(f"   Key Participants: {result['key_participants_count']}")

    except ValueError as e:
        print(f"\n❌ Error: {e}")
        print("   Please set ANTHROPIC_API_KEY environment variable or use --api-key")
        sys.exit(1)
    except Exception as e:
        logger.exception("Error during drama analysis")
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
