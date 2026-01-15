"""
Pattern libraries for multi-dimensional drama analysis.
Based on: Politeness Theory, Speech Act Theory, Argumentation frameworks, Fallacy detection.
"""

import re
from typing import List, Pattern

def compile_patterns(phrases: List[str], word_boundary: bool = True) -> List[Pattern]:
    """Compile a list of phrases into regex patterns."""
    patterns = []
    for phrase in phrases:
        if word_boundary:
            pattern = re.compile(r'\b' + re.escape(phrase) + r'\b', re.IGNORECASE)
        else:
            pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        patterns.append(pattern)
    return patterns


# =============================================================================
# POLITENESS THEORY PATTERNS (Brown & Levinson)
# =============================================================================

# Positive politeness - builds rapport, reduces drama
POSITIVE_POLITENESS = compile_patterns([
    "great point", "good point", "good idea", "nice work",
    "I agree", "you're right", "that's right", "exactly",
    "thanks for", "thank you for", "appreciate",
    "makes sense", "fair point", "fair enough",
    "well said", "good catch", "nice catch",
    "I like", "love this", "this is great"
])

# Hedges / Negative politeness - softens statements
HEDGES = compile_patterns([
    "I think", "I believe", "I feel",
    "maybe", "perhaps", "possibly",
    "might", "could be", "may be",
    "I wonder", "I'm wondering",
    "not sure", "I'm not certain",
    "it seems", "it appears", "it looks like",
    "in my opinion", "from my perspective",
    "correct me if I'm wrong", "I could be wrong",
    "if I understand correctly"
])

# Face-threatening acts (FTAs) - direct attacks on face, high drama
FACE_THREATENING = compile_patterns([
    "you're wrong", "you are wrong", "that's wrong", "that is wrong",
    "you don't understand", "you do not understand",
    "you're missing", "you are missing",
    "you failed to", "you forgot to",
    "you should have", "you should know",
    "you always", "you never",
    "obviously", "clearly you", "apparently you",
    "anyone can see", "everyone knows",
    "that's not how", "that is not how",
    "you need to", "you must", "you have to",
    "how can you", "why would you", "why didn't you"
])

# Indirect aggression - passive-aggressive, sarcastic
INDIRECT_AGGRESSION = compile_patterns([
    "with all due respect", "no offense but", "no offense,",
    "I'm just saying", "just saying",
    "interesting that you", "funny how you",
    "so you're saying", "let me get this straight",
    "if you had read", "if you actually read",
    "as I already said", "as I mentioned before",
    "I don't know how else to explain"
])


# =============================================================================
# SPEECH ACT PATTERNS (Austin/Searle)
# =============================================================================

# Directives - telling others what to do (medium-high drama potential)
DIRECTIVES = [
    re.compile(r'\byou should\b', re.I),
    re.compile(r'\byou need to\b', re.I),
    re.compile(r'\byou must\b', re.I),
    re.compile(r'\byou have to\b', re.I),
    re.compile(r'\bplease\s+(do|stop|consider|read|look)\b', re.I),
    re.compile(r'\bstop\s+\w+ing\b', re.I),
    re.compile(r"\bdon't\s+\w+\b", re.I),
    re.compile(r'\bgo\s+(read|look|check)\b', re.I),
]

# Expressives - emotional statements (high drama signal)
EXPRESSIVES = [
    re.compile(r"\bI('m| am) (frustrated|annoyed|confused|disappointed|tired)\b", re.I),
    re.compile(r"\bthis is (ridiculous|absurd|insane|crazy|nonsense|garbage)\b", re.I),
    re.compile(r"\bwhat a (waste|joke|mess)\b", re.I),
    re.compile(r"\bunbelievable\b", re.I),
    re.compile(r"\bfrustrating\b", re.I),
    re.compile(r"\bdisappointing\b", re.I),
]

# Accusations - attributing blame (very high drama)
ACCUSATIONS = [
    re.compile(r"\byou (broke|ruined|caused|created|introduced)\b", re.I),
    re.compile(r"\bthis is your (fault|mistake|problem)\b", re.I),
    re.compile(r"\byou're (the one|responsible|to blame)\b", re.I),
    re.compile(r"\bbecause of you\b", re.I),
    re.compile(r"\byou made this\b", re.I),
]

# Challenges - questioning competence (very high drama)
CHALLENGES = [
    re.compile(r"\bdo you (even|actually|really) (understand|know|read)\b", re.I),
    re.compile(r"\bhave you (even|actually|ever) (read|looked|tried|used)\b", re.I),
    re.compile(r"\bdo you understand\b", re.I),
    re.compile(r"\bcan you (even|actually)\b", re.I),
    re.compile(r"\bare you (sure|serious|kidding)\b", re.I),
]


# =============================================================================
# ARGUMENT QUALITY PATTERNS
# =============================================================================

# Evidence markers - citations, data, specifics (reduces drama, increases quality)
EVIDENCE_MARKERS = [
    re.compile(r'https?://\S+'),  # URLs
    re.compile(r'\b(BIP|PR|issue)[\s\-]?\d+\b', re.I),  # BIP-XXX, PR #123
    re.compile(r'\bcommit\s+[a-f0-9]{6,}\b', re.I),  # commit hashes
    re.compile(r'\b(the |my )?(data|benchmark|test|spec|measurement)s?\s+(show|indicate|suggest)\b', re.I),
    re.compile(r'\baccording to\b', re.I),
    re.compile(r'\bin my (testing|experience|analysis)\b', re.I),
    re.compile(r'\bmeasured\b', re.I),
    re.compile(r'\b\d+(\.\d+)?\s*(ms|MB|KB|GB|%|x faster|x slower)\b', re.I),  # metrics
]

# Acknowledgment - recognizing others' points (reduces drama)
ACKNOWLEDGMENT = compile_patterns([
    "you're right", "you are right", "that's true", "that is true",
    "fair point", "good point", "valid point",
    "I see your point", "I understand your point",
    "I agree with", "I concede", "you have a point",
    "that's a good question", "that's valid",
    "I hadn't considered", "I didn't think of",
    "you make a good point", "that's a fair criticism"
])

# Constructive proposals - offering solutions (reduces drama)
CONSTRUCTIVE = compile_patterns([
    "what if we", "what about",
    "an alternative", "another option", "alternatively",
    "we could", "we might", "we should consider",
    "I suggest", "I propose", "I recommend",
    "how about", "perhaps we could",
    "one solution", "one approach", "one way",
    "I'd be happy to", "I can", "I will",
    "let me", "I'll submit", "I'll create", "I'll open"
])

# Dismissive language (increases drama)
DISMISSIVE = compile_patterns([
    "that's wrong", "that is wrong", "wrong", "incorrect", "false",
    "no.", "nope", "nah",
    "doesn't matter", "irrelevant", "off-topic",
    "not worth", "waste of time", "pointless",
    "already addressed", "already discussed", "already answered",
    "you're missing the point", "that's not the issue",
    "I'm done", "I give up", "whatever"
])


# =============================================================================
# FALLACY PATTERNS
# =============================================================================

# Ad hominem - attacking person not argument
AD_HOMINEM = [
    re.compile(r"\byou('re| are) (just|always|never|only)\b", re.I),
    re.compile(r"\bcoming from you\b", re.I),
    re.compile(r"\bof course you('d| would)\b", re.I),
    re.compile(r"\btypical of you\b", re.I),
    re.compile(r"\bpeople like you\b", re.I),
    re.compile(r"\byou('re| are) the (kind|type|sort) of\b", re.I),
]

# Strawman - misrepresenting opponent's argument
STRAWMAN = [
    re.compile(r"\bso you('re| are) saying\b", re.I),
    re.compile(r"\bwhat you('re| are) really (saying|meaning|suggesting)\b", re.I),
    re.compile(r"\bin other words,?\s*you\b", re.I),
    re.compile(r"\blet me get this straight\b", re.I),
    re.compile(r"\bso basically you\b", re.I),
]

# Appeal to authority
APPEAL_TO_AUTHORITY = [
    re.compile(r'\b\d+\s*(years?|yrs?)\s*(of experience|experience|in)\b', re.I),
    re.compile(r"\bI('ve| have) been (doing|working|contributing)\b", re.I),
    re.compile(r"\bas a (senior|core|experienced|long-time)\b", re.I),
    re.compile(r"\bin my \d+ years\b", re.I),
    re.compile(r"\bI('ve| have) been here (since|longer)\b", re.I),
]

# Moving goalposts
MOVING_GOALPOSTS = [
    re.compile(r"\b(but |okay,?\s*)?what about\b", re.I),
    re.compile(r"\bthat('s| is) not what I meant\b", re.I),
    re.compile(r"\bI never said\b", re.I),
    re.compile(r"\byou('re| are) missing the point\b", re.I),
    re.compile(r"\bthat('s| is) not the issue\b", re.I),
]

# Whataboutism
WHATABOUTISM = [
    re.compile(r"\bwhat about (when|the time)\b", re.I),
    re.compile(r"\bbut (you|they|he|she) also\b", re.I),
    re.compile(r"\byeah but what about\b", re.I),
    re.compile(r"\bwhat about your\b", re.I),
]


# =============================================================================
# SPECIAL PATTERN DETECTION
# =============================================================================

# Stonewalling indicators - shutdown, refusal to engage
STONEWALLING = compile_patterns([
    "no.", "nope.", "wrong.", "incorrect.",
    "already addressed", "already discussed", "already answered",
    "I'm done", "done discussing", "not going to",
    "this conversation is over", "I won't", "refuse to",
    "not worth my time", "waste of time",
    "I have nothing more to say", "said all I'm going to say"
])

# Threat/ultimatum language
THREATS = compile_patterns([
    "I'll fork", "I will fork", "going to fork",
    "I'll leave", "I'm leaving", "I quit", "I'm done",
    "if this merges", "if you do this",
    "consider this my resignation", "count me out"
])

# Dismissing without engagement
DISMISS_WITHOUT_ENGAGEMENT = [
    re.compile(r"^(no|wrong|incorrect|false|nope)\.?$", re.I | re.MULTILINE),
    re.compile(r"^(nonsense|garbage|rubbish|bs)\.?$", re.I | re.MULTILINE),
    re.compile(r"\bnot even worth\b", re.I),
]
