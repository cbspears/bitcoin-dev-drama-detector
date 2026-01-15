"""
Multi-dimensional drama analyzer for Bitcoin developer discussions.

Combines multiple frameworks:
- VADER: Sentiment analysis
- TextBlob: Subjectivity detection
- Politeness Theory: Face-threatening acts, hedging
- Speech Act Theory: Directives, expressives, accusations
- Argument Quality: Evidence, acknowledgment, constructiveness
- Fallacy Detection: Ad hominem, strawman, etc.
- Special Patterns: Pile-on detection, stonewalling

Output: Simple drama/neutrality scores (0-10) backed by measurable signals.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob

from analyzer.pattern_libraries import (
    POSITIVE_POLITENESS, HEDGES, FACE_THREATENING, INDIRECT_AGGRESSION,
    DIRECTIVES, EXPRESSIVES, ACCUSATIONS, CHALLENGES,
    EVIDENCE_MARKERS, ACKNOWLEDGMENT, CONSTRUCTIVE, DISMISSIVE,
    AD_HOMINEM, STRAWMAN, APPEAL_TO_AUTHORITY, MOVING_GOALPOSTS, WHATABOUTISM,
    STONEWALLING, THREATS, DISMISS_WITHOUT_ENGAGEMENT
)


@dataclass
class DimensionalScores:
    """All dimensional scores for a piece of text."""
    # Core dimensions (0-10)
    vader_negativity: float = 0.0
    subjectivity: float = 0.0
    politeness: float = 5.0  # 5 = neutral, higher = more polite
    face_threats: float = 0.0
    argument_quality: float = 5.0
    fallacy_score: float = 0.0

    # Speech act profile (counts)
    directive_count: int = 0
    expressive_count: int = 0
    accusation_count: int = 0
    challenge_count: int = 0

    # Special patterns (boolean/counts)
    stonewalling_indicators: int = 0
    threat_indicators: int = 0

    # Composite scores (0-10)
    drama_score: float = 0.0
    neutrality_score: float = 0.0

    # Health assessment
    health_assessment: str = "unknown"

    # Evidence (for debugging, not shown to users)
    evidence: Dict = field(default_factory=dict)


class MultiDimensionalAnalyzer:
    """
    Analyzes text using multiple frameworks to produce drama/neutrality scores.

    Design philosophy:
    - Pre-process with fast, deterministic tools (VADER, TextBlob, regex)
    - Use pattern matching for specific signals
    - Combine into composite scores with explainable weights
    - Optionally enhance with Claude for nuance (separate method)
    """

    def __init__(self):
        self.vader = SentimentIntensityAnalyzer()

    def analyze(self, text: str) -> DimensionalScores:
        """
        Full multi-dimensional analysis of text.

        Args:
            text: The text to analyze (comment, message, thread)

        Returns:
            DimensionalScores with all metrics
        """
        scores = DimensionalScores()
        scores.evidence = {"text_length": len(text), "word_count": len(text.split())}

        if not text or len(text.strip()) < 10:
            return scores

        # ===== 1. VADER Sentiment =====
        vader_result = self.vader.polarity_scores(text)
        # Convert compound (-1 to +1) to negativity (0 to 10)
        # compound of -1 = negativity of 10, compound of +1 = negativity of 0
        scores.vader_negativity = round((1 - vader_result['compound']) * 5, 2)
        scores.evidence['vader'] = vader_result

        # ===== 2. TextBlob Subjectivity =====
        blob = TextBlob(text)
        scores.subjectivity = round(blob.sentiment.subjectivity * 10, 2)
        scores.evidence['textblob'] = {
            'polarity': round(blob.sentiment.polarity, 3),
            'subjectivity': round(blob.sentiment.subjectivity, 3)
        }

        # ===== 3. Politeness Analysis =====
        positive_count = self._count_patterns(text, POSITIVE_POLITENESS)
        hedge_count = self._count_patterns(text, HEDGES)
        fta_count = self._count_patterns(text, FACE_THREATENING)
        indirect_agg_count = self._count_patterns(text, INDIRECT_AGGRESSION)

        # Politeness score: more positive/hedges = higher, more FTAs = lower
        politeness_raw = (positive_count * 2 + hedge_count) - (fta_count * 2 + indirect_agg_count * 1.5)
        scores.politeness = round(max(0, min(10, 5 + politeness_raw)), 2)
        scores.face_threats = round(min(10, (fta_count + indirect_agg_count) * 2), 2)

        scores.evidence['politeness'] = {
            'positive_markers': positive_count,
            'hedges': hedge_count,
            'face_threatening': fta_count,
            'indirect_aggression': indirect_agg_count
        }

        # ===== 4. Speech Act Analysis =====
        scores.directive_count = self._count_patterns(text, DIRECTIVES)
        scores.expressive_count = self._count_patterns(text, EXPRESSIVES)
        scores.accusation_count = self._count_patterns(text, ACCUSATIONS)
        scores.challenge_count = self._count_patterns(text, CHALLENGES)

        scores.evidence['speech_acts'] = {
            'directives': scores.directive_count,
            'expressives': scores.expressive_count,
            'accusations': scores.accusation_count,
            'challenges': scores.challenge_count
        }

        # ===== 5. Argument Quality =====
        evidence_count = self._count_patterns(text, EVIDENCE_MARKERS)
        ack_count = self._count_patterns(text, ACKNOWLEDGMENT)
        constructive_count = self._count_patterns(text, CONSTRUCTIVE)
        dismissive_count = self._count_patterns(text, DISMISSIVE)

        # Quality score: evidence + acknowledgment + constructive - dismissive
        quality_raw = (evidence_count * 2 + ack_count * 2 + constructive_count * 1.5) - (dismissive_count * 2)
        scores.argument_quality = round(max(0, min(10, 5 + quality_raw)), 2)

        scores.evidence['argument_quality'] = {
            'evidence_citations': evidence_count,
            'acknowledgments': ack_count,
            'constructive': constructive_count,
            'dismissive': dismissive_count
        }

        # ===== 6. Fallacy Detection =====
        ad_hom = self._count_patterns(text, AD_HOMINEM)
        strawman = self._count_patterns(text, STRAWMAN)
        authority = self._count_patterns(text, APPEAL_TO_AUTHORITY)
        goalposts = self._count_patterns(text, MOVING_GOALPOSTS)
        whatabout = self._count_patterns(text, WHATABOUTISM)

        total_fallacies = ad_hom + strawman + authority + goalposts + whatabout
        scores.fallacy_score = round(min(10, total_fallacies * 2.5), 2)

        scores.evidence['fallacies'] = {
            'ad_hominem': ad_hom,
            'strawman': strawman,
            'appeal_to_authority': authority,
            'moving_goalposts': goalposts,
            'whataboutism': whatabout,
            'total': total_fallacies
        }

        # ===== 7. Special Patterns =====
        scores.stonewalling_indicators = self._count_patterns(text, STONEWALLING)
        scores.stonewalling_indicators += self._count_patterns(text, DISMISS_WITHOUT_ENGAGEMENT)
        scores.threat_indicators = self._count_patterns(text, THREATS)

        scores.evidence['special'] = {
            'stonewalling': scores.stonewalling_indicators,
            'threats': scores.threat_indicators
        }

        # ===== 8. Calculate Composite Scores =====
        scores = self._calculate_composite_scores(scores)

        return scores

    def _count_patterns(self, text: str, patterns: List) -> int:
        """Count how many patterns match in the text."""
        count = 0
        for pattern in patterns:
            if isinstance(pattern, re.Pattern):
                count += len(pattern.findall(text))
            else:
                # It's a compiled pattern from compile_patterns()
                count += len(pattern.findall(text))
        return count

    def _calculate_composite_scores(self, scores: DimensionalScores) -> DimensionalScores:
        """Calculate final drama and neutrality scores from dimensions."""

        # High-drama speech acts contribute to drama
        speech_act_drama = min(10, (
            scores.accusation_count * 3 +
            scores.challenge_count * 2.5 +
            scores.expressive_count * 1.5 +
            scores.directive_count * 0.5
        ))

        # Stonewalling is a strong drama signal
        stonewalling_penalty = min(3, scores.stonewalling_indicators * 1.5)

        # DRAMA SCORE FORMULA
        # Weights sum to 1.0
        scores.drama_score = round(
            scores.vader_negativity * 0.20 +           # Sentiment
            (10 - scores.politeness) * 0.20 +          # Impoliteness
            scores.face_threats * 0.15 +               # Direct FTAs
            scores.subjectivity * 0.10 +               # Opinion vs fact
            scores.fallacy_score * 0.15 +              # Logical fallacies
            (10 - scores.argument_quality) * 0.10 +    # Low quality
            speech_act_drama * 0.10                    # Accusation/challenges
        , 2)

        # Add stonewalling as additive penalty
        scores.drama_score = round(min(10, scores.drama_score + stonewalling_penalty), 2)

        # NEUTRALITY SCORE FORMULA
        scores.neutrality_score = round(
            (10 - scores.subjectivity) * 0.30 +        # Objectivity
            scores.argument_quality * 0.30 +            # Evidence-based
            scores.politeness * 0.20 +                  # Respectful
            (10 - scores.fallacy_score) * 0.10 +       # Logical
            (10 - scores.face_threats) * 0.10          # Non-threatening
        , 2)

        # HEALTH ASSESSMENT
        if scores.drama_score >= 6 and scores.neutrality_score < 5:
            scores.health_assessment = "toxic"
        elif scores.drama_score >= 5 and scores.neutrality_score >= 5:
            scores.health_assessment = "heated-but-fair"
        elif scores.drama_score < 4 and scores.neutrality_score >= 6:
            scores.health_assessment = "productive"
        elif scores.drama_score < 4 and scores.neutrality_score < 5:
            scores.health_assessment = "dismissive"
        else:
            scores.health_assessment = "mixed"

        return scores

    def analyze_thread(self, messages: List[Dict]) -> Dict:
        """
        Analyze a full thread of messages.

        Args:
            messages: List of {"author": str, "content": str, "timestamp": str}

        Returns:
            Thread-level analysis including pile-on detection
        """
        if not messages:
            return {"drama_score": 0, "neutrality_score": 5, "health": "empty"}

        # Analyze each message
        message_scores = []
        author_scores = {}

        for msg in messages:
            score = self.analyze(msg.get('content', ''))
            message_scores.append(score)

            author = msg.get('author', 'unknown')
            if author not in author_scores:
                author_scores[author] = []
            author_scores[author].append(score)

        # Thread-level metrics
        drama_scores = [s.drama_score for s in message_scores]
        neutrality_scores = [s.neutrality_score for s in message_scores]

        avg_drama = sum(drama_scores) / len(drama_scores)
        avg_neutrality = sum(neutrality_scores) / len(neutrality_scores)
        max_drama = max(drama_scores)

        # Pile-on detection
        # High drama + many unique authors + clustered timing = pile-on
        unique_authors = len(author_scores)
        is_pile_on = (
            avg_drama > 5 and
            unique_authors > 5 and
            max_drama > 7
        )

        # Per-author analysis
        author_analysis = {}
        for author, scores_list in author_scores.items():
            author_drama = sum(s.drama_score for s in scores_list) / len(scores_list)
            author_neutrality = sum(s.neutrality_score for s in scores_list) / len(scores_list)
            stonewalling = sum(s.stonewalling_indicators for s in scores_list)

            author_analysis[author] = {
                "message_count": len(scores_list),
                "avg_drama": round(author_drama, 2),
                "avg_neutrality": round(author_neutrality, 2),
                "stonewalling_indicators": stonewalling,
                "is_difficult": stonewalling > 2 or (author_drama > 6 and author_neutrality < 4)
            }

        return {
            "thread_drama_score": round(avg_drama, 2),
            "thread_neutrality_score": round(avg_neutrality, 2),
            "max_drama": round(max_drama, 2),
            "message_count": len(messages),
            "unique_authors": unique_authors,
            "is_pile_on": is_pile_on,
            "health_assessment": self._assess_thread_health(avg_drama, avg_neutrality),
            "author_analysis": author_analysis,
            "difficult_participants": [
                author for author, data in author_analysis.items()
                if data.get("is_difficult", False)
            ]
        }

    def _assess_thread_health(self, drama: float, neutrality: float) -> str:
        """Assess overall thread health."""
        if drama >= 6 and neutrality < 5:
            return "toxic"
        elif drama >= 5 and neutrality >= 5:
            return "heated-but-fair"
        elif drama < 4 and neutrality >= 6:
            return "productive"
        elif drama < 4 and neutrality < 5:
            return "dismissive"
        return "mixed"


# =============================================================================
# PARTICIPANT PROFILING
# =============================================================================

@dataclass
class ParticipantProfile:
    """Profile of a participant's communication patterns."""
    handle: str
    message_count: int = 0

    # Average scores
    avg_drama: float = 0.0
    avg_neutrality: float = 0.0
    avg_politeness: float = 5.0
    avg_argument_quality: float = 5.0
    avg_subjectivity: float = 5.0
    avg_fallacy_rate: float = 0.0
    avg_face_threats: float = 0.0

    # Speech act profile (percentages)
    directive_rate: float = 0.0
    expressive_rate: float = 0.0
    accusation_rate: float = 0.0

    # Special flags
    total_stonewalling: int = 0
    is_difficult: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "handle": self.handle,
            "message_count": self.message_count,
            "scores": {
                "drama": round(self.avg_drama, 2),
                "neutrality": round(self.avg_neutrality, 2),
                "politeness": round(self.avg_politeness, 2),
                "argument_quality": round(self.avg_argument_quality, 2),
                "subjectivity": round(self.avg_subjectivity, 2),
                "fallacy_rate": round(self.avg_fallacy_rate, 2),
                "face_threats": round(self.avg_face_threats, 2)
            },
            "speech_act_profile": {
                "directive_rate": round(self.directive_rate, 2),
                "expressive_rate": round(self.expressive_rate, 2),
                "accusation_rate": round(self.accusation_rate, 2)
            },
            "flags": {
                "stonewalling_total": self.total_stonewalling,
                "is_difficult": self.is_difficult
            }
        }


class ParticipantProfiler:
    """Builds and maintains profiles for participants."""

    def __init__(self, analyzer: MultiDimensionalAnalyzer):
        self.analyzer = analyzer
        self.profiles: Dict[str, ParticipantProfile] = {}
        self._score_history: Dict[str, List[DimensionalScores]] = {}

    def add_message(self, handle: str, content: str):
        """Add a message to a participant's profile."""
        scores = self.analyzer.analyze(content)

        if handle not in self.profiles:
            self.profiles[handle] = ParticipantProfile(handle=handle)
            self._score_history[handle] = []

        self._score_history[handle].append(scores)
        self._update_profile(handle)

    def _update_profile(self, handle: str):
        """Recalculate profile from score history."""
        history = self._score_history[handle]
        profile = self.profiles[handle]

        n = len(history)
        profile.message_count = n

        if n == 0:
            return

        # Calculate averages
        profile.avg_drama = sum(s.drama_score for s in history) / n
        profile.avg_neutrality = sum(s.neutrality_score for s in history) / n
        profile.avg_politeness = sum(s.politeness for s in history) / n
        profile.avg_argument_quality = sum(s.argument_quality for s in history) / n
        profile.avg_subjectivity = sum(s.subjectivity for s in history) / n
        profile.avg_fallacy_rate = sum(s.fallacy_score for s in history) / n
        profile.avg_face_threats = sum(s.face_threats for s in history) / n

        # Speech act rates
        total_speech_acts = sum(
            s.directive_count + s.expressive_count + s.accusation_count + s.challenge_count
            for s in history
        ) or 1  # Avoid division by zero

        profile.directive_rate = sum(s.directive_count for s in history) / total_speech_acts * 100
        profile.expressive_rate = sum(s.expressive_count for s in history) / total_speech_acts * 100
        profile.accusation_rate = sum(s.accusation_count for s in history) / total_speech_acts * 100

        # Stonewalling
        profile.total_stonewalling = sum(s.stonewalling_indicators for s in history)

        # Is difficult?
        profile.is_difficult = (
            profile.total_stonewalling > 3 or
            (profile.avg_drama > 6 and profile.avg_neutrality < 4) or
            profile.accusation_rate > 20
        )

    def get_profile(self, handle: str) -> Optional[ParticipantProfile]:
        """Get a participant's profile."""
        return self.profiles.get(handle)

    def get_all_profiles(self) -> Dict[str, Dict]:
        """Get all profiles as dictionaries."""
        return {
            handle: profile.to_dict()
            for handle, profile in self.profiles.items()
        }

    def get_difficult_participants(self) -> List[str]:
        """Get list of participants flagged as difficult."""
        return [
            handle for handle, profile in self.profiles.items()
            if profile.is_difficult
        ]


# =============================================================================
# USAGE EXAMPLE
# =============================================================================

if __name__ == "__main__":
    # Initialize analyzer
    analyzer = MultiDimensionalAnalyzer()

    # Test with sample texts
    samples = [
        # Toxic
        """
        You clearly don't understand how Bitcoin works. This proposal is ridiculous
        and anyone who's spent more than 5 minutes thinking about it would see that.
        I've been working on this codebase for 8 years and this is one of the worst
        ideas I've seen.
        """,

        # Productive
        """
        I see your point about the performance implications. Looking at the benchmarks
        in PR #28421, it seems like there might be a 15% overhead. What if we tried
        caching the intermediate results? I can submit a proof of concept if that
        would help move the discussion forward.
        """,

        # Stonewalling
        """
        No. Already discussed. Not going to repeat myself. If you had read the
        previous threads you would know why this doesn't work. Waste of time.
        """,

        # Heated but fair
        """
        I strongly disagree with this approach - I think it fundamentally misunderstands
        the security model. However, I acknowledge you've put significant work into this.
        The specific issue is that soft forks shouldn't require... [technical argument].
        Have you considered the alternative proposed in BIP-XXX?
        """
    ]

    print("=" * 60)
    print("Multi-Dimensional Drama Analyzer Test")
    print("=" * 60)

    for i, text in enumerate(samples):
        print(f"\n--- Sample {i+1} ---")
        scores = analyzer.analyze(text)
        print(f"Drama Score:      {scores.drama_score}/10")
        print(f"Neutrality Score: {scores.neutrality_score}/10")
        print(f"Health:           {scores.health_assessment}")
        print(f"\nDimensional Breakdown:")
        print(f"  VADER Negativity: {scores.vader_negativity}/10")
        print(f"  Subjectivity:     {scores.subjectivity}/10")
        print(f"  Politeness:       {scores.politeness}/10")
        print(f"  Face Threats:     {scores.face_threats}/10")
        print(f"  Argument Quality: {scores.argument_quality}/10")
        print(f"  Fallacy Score:    {scores.fallacy_score}/10")
        print(f"  Stonewalling:     {scores.stonewalling_indicators} indicators")
