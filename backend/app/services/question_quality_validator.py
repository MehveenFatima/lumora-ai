"""
LumoraAI - Question Quality & Anti-Leakage Validator
=====================================================
Validates generated multiple-choice assessment questions:
1. Prevents answer leakage (verbatim answer in stem, high token overlap, n-gram copying).
2. Prevents citation metadata leakage into question stems (filenames, page numbers).
3. Prevents raw source passage dumping into question stems.
4. Enforces distractor quality and option length balance.
5. Computes a multi-signal question quality score in [0.0, 1.0].
6. Allows legitimate shared terminology (e.g. concept names like 'BFS', 'QuickSort').
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import re
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    is_valid: bool
    quality_score: float  # 0.0 to 1.0
    leakage_score: float  # 0.0 (no leakage) to 1.0 (complete leakage)
    rejection_reasons: List[str] = field(default_factory=list)
    quality_notes: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


# Standard evaluation stopwords that don't carry conceptual meaning
COMMON_STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's",
    "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than",
    "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there",
    "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's",
    "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom",
    "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll",
    "you're", "you've", "your", "yours", "yourself", "yourselves",
    # Question framing boilerplate
    "which", "following", "statements", "statement", "describes", "best", "correct",
    "true", "false", "characterized", "characterize", "regarding", "respect", "context",
}

# Regex patterns for detecting citation metadata leaking into question stems
CITATION_LEAK_PATTERNS = [
    re.compile(r"\bpage\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bon\s+page\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bpage\s*\d+\s*[:\-–]", re.IGNORECASE),
    re.compile(r"\bpages\s+\d+\s*(?:to|-|–)\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bslide\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bunit\s*[-–]?\s*\d+\b", re.IGNORECASE),
    re.compile(r"\bchapter\s+\d+\b", re.IGNORECASE),
    re.compile(r"\bsection\s+\d+\b", re.IGNORECASE),
    re.compile(r"\b\w+\.(?:pdf|docx|pptx|txt)\b", re.IGNORECASE),
    re.compile(r"according\s+to\s+[A-Za-z0-9_\-\s]+(?:\.pdf|page|\(page)", re.IGNORECASE),
    re.compile(r"how\s+does\s+[A-Za-z0-9_\-\s]+(?:\.pdf|page)\s+characterize", re.IGNORECASE),
]

# Patterns for detecting raw Markdown tables, code snippets, and parser garbage
PARSER_GARBAGE_PATTERNS = [
    re.compile(r"\|.*\|", re.DOTALL),             # Markdown table pipes
    re.compile(r"\|\s*[-:]+\s*\|"),                # Markdown table divider rows
    re.compile(r"```"),                            # Code fences
    re.compile(r"#!\s*/usr/"),                     # Shebang
    re.compile(r"\b(?:=begin|=end)\b"),            # Ruby block comments
    re.compile(r"<(?:div|h[1-6]|table|tr|td|th|p|span|br|pre|code)[^>]*>", re.IGNORECASE),  # HTML tags
    re.compile(r"\b(?:gem\s+install|bundle\s+exec|Procfile)\b", re.IGNORECASE),             # Shell/deploy tooling
    re.compile(r"\b(?:require\s+['\"][a-zA-Z0-9_\-]+['\"]|import\s+[a-zA-Z0-9_]+)\b"),     # Script imports
    re.compile(r"#{1,6}\s+[A-Za-z0-9_]"),          # Markdown headings (### ...)
    re.compile(r"\bExtracted\s+Tables?\b", re.IGNORECASE),  # Parser artifact
    re.compile(r"\bStatement\s+(?:n|\d+)\b", re.IGNORECASE), # Parser artifact
]

GENERIC_CONCEPT_BLACKLIST = frozenset({
    "page", "pages", "unit", "chapter", "section", "topic", "topics", "example", "examples",
    "syntax", "code", "table", "figure", "notes", "file", "general", "core principle",
    "workspace document", "introduction", "overview", "summary", "basics",
})

GENERIC_CONCEPT_PREFIX_PATTERNS = [
    re.compile(r"^\s*(?:basics\s+of|introduction\s+to|overview\s+of|fundamentals\s+of|guide\s+to|notes\s+on|chapter\s+on|section\s+on|discussion\s+on|summary\s+of|details\s+of)\s+", re.IGNORECASE),
]

INSTRUCTIONAL_HEADING_PATTERNS = [
    re.compile(r"^\s*here(?:'s|\s+is)\s+how\b", re.IGNORECASE),
    re.compile(r"^\s*how\s+to\b", re.IGNORECASE),
    re.compile(r"^\s*in\s+this\s+(?:section|chapter|unit|document|guide|tutorial|module)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:for\s+example|example\s*\d*[:\-–]|e\.g\.)\b", re.IGNORECASE),
    re.compile(r"^\s*let(?:'s|\s+us)\s+(?:look|see|examine|explore|consider)\b", re.IGNORECASE),
    re.compile(r"^\s*consider\s+the\s+following\b", re.IGNORECASE),
    re.compile(r"^\s*the\s+following\s+(?:code|example|section|figure|table)\b", re.IGNORECASE),
    re.compile(r"^\s*step\s+\d+\s*[:\-–]", re.IGNORECASE),
    re.compile(r"^\s*see\s+(?:section|chapter|page|figure|table|slide)\b", re.IGNORECASE),
    re.compile(r"^\s*(?:click\s+on|run\s+the\s+command|open\s+the\s+file|download|install)\b", re.IGNORECASE),
    re.compile(r"^\s*as\s+shown\s+in\b", re.IGNORECASE),
]

STEM_ROLE_PURPOSE_PATTERNS = [
    re.compile(r"\barchitectural\s+responsibility\b", re.IGNORECASE),
    re.compile(r"\bcore\s+responsibility\b", re.IGNORECASE),
    re.compile(r"\bprimary\s+responsibility\b", re.IGNORECASE),
    re.compile(r"\bprimary\s+purpose\b", re.IGNORECASE),
    re.compile(r"\bcore\s+purpose\b", re.IGNORECASE),
    re.compile(r"\boperational\s+role\b", re.IGNORECASE),
    re.compile(r"\bprimary\s+role\b", re.IGNORECASE),
    re.compile(r"\bprogrammatic\s+role\b", re.IGNORECASE),
    re.compile(r"\bfunctional\s+role\b", re.IGNORECASE),
    re.compile(r"\bprimary\s+objective\b", re.IGNORECASE),
    re.compile(r"\bfoundational\s+objective\b", re.IGNORECASE),
]

PROMPT_LEAK_PATTERNS = [
    re.compile(r"^(?:here is a question|based on the provided context|according to the text|question:|as an ai)\b", re.IGNORECASE),
    re.compile(r"\b(?:json format|output format|return a json)\b", re.IGNORECASE),
]


QUESTION_TYPES = [
    "conceptual",
    "comparison",
    "application",
    "scenario",
    "reasoning",
    "trace_output",
    "interpretation",
    "edge_case",
    "complexity_analysis",
]


class QuestionQualityValidator:
    """
    Validates question stems and options against answer leakage, citation contamination,
    source passage dumping, and option imbalance.
    """

    def __init__(
        self,
        min_quality_threshold: float = 0.70,
        max_leakage_threshold: float = 0.35,
        max_token_overlap_threshold: float = 0.50,
        min_ngram_leak_size: int = 4,
    ):
        self.min_quality_threshold = min_quality_threshold
        self.max_leakage_threshold = max_leakage_threshold
        self.max_token_overlap_threshold = max_token_overlap_threshold
        self.min_ngram_leak_size = min_ngram_leak_size

    @staticmethod
    def normalize_text(text: str) -> str:
        """Lowercases, removes punctuation, and condenses spaces."""
        if not text:
            return ""
        t = text.lower()
        t = re.sub(r"[^\w\s]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    @classmethod
    def extract_content_tokens(
        cls,
        text: str,
        exclude_concept: Optional[str] = None,
    ) -> Set[str]:
        """Extracts substantive content tokens, removing common stopwords and optional concept tokens."""
        norm = cls.normalize_text(text)
        tokens = set(w for w in norm.split() if len(w) > 2 and w not in COMMON_STOPWORDS)

        if exclude_concept:
            concept_tokens = set(cls.normalize_text(exclude_concept).split())
            tokens = tokens - concept_tokens

        return tokens

    def check_verbatim_leakage(
        self,
        stem: str,
        correct_text: str,
        options: List[Dict[str, str]],
    ) -> Tuple[bool, Optional[str]]:
        """
        Rejects if:
        1. Correct answer is a verbatim substring of the stem (length > 12).
        2. Any option is quoted verbatim inside the stem (length > 15).
        """
        norm_stem = self.normalize_text(stem)
        norm_correct = self.normalize_text(correct_text)

        if len(norm_correct) >= 6 and norm_correct in norm_stem:
            return True, f"Question stem contains the complete correct answer verbatim: '{correct_text[:60]}...'"

        for opt in options:
            opt_text = opt.get("text", "").strip()
            norm_opt = self.normalize_text(opt_text)
            if len(norm_opt) >= 15 and norm_opt in norm_stem:
                return True, f"Option '{opt.get('key')}' is quoted verbatim in the question stem."

        return False, None

    def check_ngram_leakage(
        self,
        stem: str,
        correct_text: str,
        concept: Optional[str] = None,
        n: int = 4,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if a contiguous sequence of n content words from the answer appears verbatim in the stem.
        Ignores phrases that are merely the concept name itself.
        """
        norm_stem_words = self.normalize_text(stem).split()
        norm_ans_words = self.normalize_text(correct_text).split()

        norm_concept = self.normalize_text(concept) if concept else ""

        if len(norm_ans_words) < n or len(norm_stem_words) < n:
            return False, None

        # Generate n-grams from correct answer
        stem_ngrams = set(
            " ".join(norm_stem_words[i : i + n])
            for i in range(len(norm_stem_words) - n + 1)
        )

        for i in range(len(norm_ans_words) - n + 1):
            ngram = " ".join(norm_ans_words[i : i + n])
            # If the n-gram is essentially the concept name, legitimate
            if norm_concept and (ngram in norm_concept or norm_concept in ngram):
                continue
            # If n-gram consists only of stopwords, skip
            ngram_words = set(ngram.split())
            if not (ngram_words - COMMON_STOPWORDS):
                continue

            if ngram in stem_ngrams:
                return True, f"Question stem contains verbatim {n}-word answer phrase: '{ngram}'"

        return False, None

    def check_token_overlap(
        self,
        stem: str,
        correct_text: str,
        concept: Optional[str] = None,
    ) -> Tuple[float, bool, Optional[str]]:
        """
        Calculates content token overlap between stem and answer (excluding legitimate shared concept tokens).
        Returns (overlap_ratio, is_excessive, error_msg).
        """
        stem_tokens = self.extract_content_tokens(stem, exclude_concept=concept)
        ans_tokens = self.extract_content_tokens(correct_text, exclude_concept=concept)

        if not ans_tokens:
            return 0.0, False, None

        shared = stem_tokens.intersection(ans_tokens)
        overlap_ratio = len(shared) / len(ans_tokens)

        if overlap_ratio > self.max_token_overlap_threshold:
            shared_words = ", ".join(list(shared)[:5])
            return overlap_ratio, True, f"Excessive non-concept token overlap ({overlap_ratio:.0%}): shared [{shared_words}]"

        return overlap_ratio, False, None

    def check_citation_leakage(
        self,
        stem: str,
        document_name: Optional[str] = None,
        options: Optional[List[Dict[str, str]]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if document citations, page numbers, or file names have leaked into the question stem or options.
        """
        texts_to_check = [("Question stem", stem)]
        if options:
            for opt in options:
                texts_to_check.append((f"Option '{opt.get('key')}'", opt.get("text", "")))

        for label, text in texts_to_check:
            if not text:
                continue
            if document_name:
                clean_doc = document_name.strip()
                if clean_doc.lower() in text.lower() and len(clean_doc) > 3:
                    return True, f"{label} contains citation document name '{clean_doc}'."

            for pattern in CITATION_LEAK_PATTERNS:
                match = pattern.search(text)
                if match:
                    return True, f"{label} contains citation metadata: '{match.group(0)}'."

        return False, None

    def check_source_dump(
        self,
        stem: str,
        source_excerpt: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if a raw source passage was dumped directly into the stem rather than formulating
        an independent conceptual question.
        """
        # 1. Check for raw code keywords and syntax patterns directly dumped into the stem
        code_indicators = [
            r"\brequire\s+['\"][a-zA-Z0-9_\-]+['\"]",
            r"\bimport\s+[a-zA-Z0-9_]+",
            r"[a-zA-Z0-9_]+\s*=\s*[A-Z][a-zA-Z0-9_]*\.new\b",
            r"\bdef\s+[a-zA-Z0-9_]+\s*\(",
            r"\bclass\s+[A-Z][a-zA-Z0-9_]*",
            r"\{\s*title\s+['\"][^'\"]+['\"]\s*\}",
            r"\b[A-Z][a-zA-Z0-9_]*\.[a-z0-9_]+\b(?:\s*\(.*?\))?",
        ]
        for pattern in code_indicators:
            match = re.search(pattern, stem)
            if match and len(match.group(0)) > 6:
                return True, f"Question stem contains raw code snippet or program syntax: '{match.group(0)}'"

        if not source_excerpt:
            return False, None

        norm_stem = self.normalize_text(stem)
        norm_source = self.normalize_text(source_excerpt)

        # Check for long contiguous chunks (>= 8 words) from source in stem
        source_words = norm_source.split()
        if len(source_words) >= 8:
            for i in range(len(source_words) - 7):
                chunk_8 = " ".join(source_words[i : i + 8])
                if chunk_8 in norm_stem and len(chunk_8) > 25:
                    return True, f"Question stem copies raw 8-word source passage: '{chunk_8}'"

        # Check overall token overlap with source
        stem_tokens = self.extract_content_tokens(stem)
        src_tokens = self.extract_content_tokens(source_excerpt)
        if stem_tokens and src_tokens:
            overlap = len(stem_tokens.intersection(src_tokens)) / len(stem_tokens)
            if overlap > 0.70 and len(stem_tokens) > 10:
                return True, f"Question stem is an excessive verbatim copy of the source context ({overlap:.0%} overlap)."

        return False, None

    def check_option_balance(
        self,
        options: List[Dict[str, str]],
        correct_key: str,
    ) -> Tuple[float, List[str]]:
        """
        Evaluates option balance:
        - Mutual distinctness (no duplicates).
        - Relative length: correct answer shouldn't be significantly longer than distractors.
        Returns (balance_score, warning_notes).
        """
        notes = []
        score = 1.0

        texts = [opt.get("text", "").strip() for opt in options]

        # Check distinctness
        norm_texts = [self.normalize_text(t) for t in texts]
        if len(set(norm_texts)) != len(norm_texts):
            notes.append("Options contain duplicate or near-identical text.")
            return 0.0, notes

        # Find correct answer
        correct_opt = next((opt for opt in options if opt.get("key") == correct_key), None)
        if not correct_opt:
            notes.append(f"Correct option key '{correct_key}' not found in options.")
            return 0.0, notes

        correct_len = len(correct_opt.get("text", ""))
        distractor_lens = [len(opt.get("text", "")) for opt in options if opt.get("key") != correct_key]

        if distractor_lens:
            avg_dist_len = sum(distractor_lens) / len(distractor_lens)
            if avg_dist_len > 0:
                ratio = correct_len / avg_dist_len
                if ratio > 2.5:
                    score -= 0.35
                    notes.append(f"Correct answer is suspiciously longer ({ratio:.1f}x) than average distractor.")
                elif ratio < 0.35:
                    score -= 0.25
                    notes.append(f"Correct answer is suspiciously shorter ({ratio:.1f}x) than average distractor.")

        return max(0.0, score), notes

    def check_instructional_or_heading_answer(
        self,
        correct_text: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if the correct answer is merely an instructional sentence, conversational hook,
        or tutorial heading (e.g. 'Here's how to...', 'How to...', 'Example:', 'Step 1:'),
        which is copied raw from textbook sections rather than being a valid conceptual answer.
        """
        for pat in INSTRUCTIONAL_HEADING_PATTERNS:
            if pat.search(correct_text):
                return True, f"Correct option is an instructional tutorial heading or conversational phrase: '{correct_text[:60]}...'"
        return False, None

    def check_concept_naming_quality(
        self,
        concept: Optional[str],
        stem: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if the target concept or question stem embeds generic section prefixes
        like 'Basics of...', 'Introduction to...', 'Overview of...'.
        """
        if concept:
            for pat in GENERIC_CONCEPT_PREFIX_PATTERNS:
                if pat.search(concept):
                    return True, f"Target concept '{concept}' embeds a generic document division prefix (e.g. 'Basics of')."
        stem_lower = stem.lower()
        for pat in GENERIC_CONCEPT_PREFIX_PATTERNS:
            match = pat.search(stem_lower)
            if match:
                return True, f"Question stem embeds a generic document division prefix: '{match.group(0).strip()}'."
            if "by basics of " in stem_lower or "by introduction to " in stem_lower:
                return True, "Question stem embeds a generic document division heading ('Basics of / Introduction to')."
        return False, None

    def check_semantic_stem_answer_compatibility(
        self,
        stem: str,
        correct_text: str,
        options: List[Dict[str, str]],
        concept: Optional[str] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifies that the correct answer semantically and structurally answers the question stem.
        Rejects when:
        1. Stem asks for an architectural responsibility / role / purpose, but answer is an instructional heading or fragment.
        2. Stem asks about one cognitive intent (e.g. role, mechanism) but answer belongs to an unrelated semantic category.
        3. Option can be answered by recognizing copied phrasing rather than understanding the concept.
        """
        stem_lower = stem.lower()
        ans_lower = correct_text.lower().strip()

        # 1. Architectural responsibility / purpose / role questions
        is_role_question = any(pat.search(stem) for pat in STEM_ROLE_PURPOSE_PATTERNS)
        if is_role_question:
            if any(ans_lower.startswith(prefix) for prefix in [
                "here's how", "here is how", "how to", "in this section", "for example",
                "let's", "consider", "step 1", "click on", "run the", "open the"
            ]):
                return True, f"Question asks for an architectural responsibility/purpose, but correct option is an instructional tutorial heading: '{correct_text[:60]}...'"

            if ans_lower.startswith("read ") or ans_lower.startswith("write ") or ans_lower.startswith("get ") or ans_lower.startswith("set "):
                if len(ans_lower.split()) < 5:
                    return True, f"Correct option is a brief command/action ('{correct_text}') rather than a substantive architectural responsibility."

        # 2. Complexity analysis questions
        is_complexity_question = any(kw in stem_lower for kw in [
            "computational efficiency", "resource trade-off", "runtime scaling",
            "complexity bound", "performance constraint"
        ])
        if is_complexity_question:
            has_complexity_term = any(term in ans_lower for term in [
                "o(", "logarithmic", "linear", "quadratic", "constant", "exponential",
                "worst-case", "average-case", "amortized", "space complexity", "time complexity",
                "trade-off", "bound", "memory footprint", "latency"
            ])
            if not has_complexity_term:
                return True, f"Question asks for complexity/performance constraint, but correct option does not contain complexity bounds: '{correct_text[:60]}...'"

        # 3. Cryptographic / Security guarantee questions
        is_crypto_guarantee = any(kw in stem_lower for kw in [
            "cryptographic integrity", "security guarantee", "prevent unauthorized",
            "mitigate adversarial", "cryptographic property"
        ])
        if is_crypto_guarantee:
            has_sec_term = any(term in ans_lower for term in [
                "encrypt", "cipher", "mac", "hmac", "integrity", "confidentiality",
                "tampering", "authentication", "signature", "certificate", "nonce",
                "replay", "key exchange", "hash", "secret", "secrecy", "handshake",
                "security", "protocol", "alert", "closure", "notification", "key",
                "compromise", "protect", "transmit", "channel", "parameter"
            ])
            if not has_sec_term:
                return True, f"Question asks for cryptographic security guarantee, but correct option lacks security mechanisms: '{correct_text[:60]}...'"

        return False, None

    def check_unusual_token_and_code_leakage(
        self,
        stem: str,
        options: List[Dict[str, str]],
        correct_key: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if one option is dramatically more distinctive because it contains code syntax,
        brackets, assignment operators, filenames, commands, or unusual source wording while distractors do not,
        making the correct answer trivially identifiable without understanding the concept.

        Allows code syntax when the question stem genuinely tests code/syntax.
        """
        code_syntax_patterns = [
            r"\[.*?\]",               # Array brackets e.g. params['val']
            r"\{.*?\}",               # Curly braces / blocks
            r"[a-zA-Z0-9_]+\s*=\s*",  # Variable assignment
            r"->|::|=>",              # Code operators
            r"\bdef\s+[a-zA-Z0-9_]+", # Method definition
            r"\bclass\s+[A-Z]",       # Class definition
            r"\$[a-zA-Z0-9_]+",       # Shell/global variable
            r"@[a-zA-Z0-9_]+",        # Instance variable
            r"\b[a-zA-Z0-9_]+\.[a-z0-9_]+\(.*?\)", # Method call with parens
        ]
        code_regex = re.compile("|".join(code_syntax_patterns))

        stem_lower = stem.lower()
        is_code_question = any(kw in stem_lower for kw in [
            "syntax", "code", "keyword", "method", "function", "expression",
            "snippet", "statement", "command", "implementation", "call", "declaration",
            "trace", "output", "returns", "parameter", "which of the following creates",
            "which code", "how do you"
        ])

        opt_has_code = []
        for opt in options:
            t = opt.get("text", "")
            has_c = bool(code_regex.search(t))
            opt_has_code.append((opt.get("key"), has_c))

        code_count = sum(1 for _, has_c in opt_has_code if has_c)

        if not is_code_question:
            if code_count == 1:
                leaked_key = next(k for k, has_c in opt_has_code if has_c)
                if leaked_key == correct_key:
                    return True, "Correct option is leaked by distinctive code/syntax tokens while distractors are plain prose statements."
                else:
                    return True, "Option structural imbalance: one distractor uniquely contains code syntax."
        else:
            if code_count == 1 and opt_has_code[0][0] == correct_key:
                return True, "Option structural imbalance in code question: correct option is code syntax while distractors are generic prose."

        return False, None

    def check_distractor_structural_balance(
        self,
        options: List[Dict[str, str]],
        correct_key: str,
    ) -> Tuple[bool, Optional[str]]:
        """
        Detects if option grammatical structure or category makes the correct answer trivially identifiable.
        E.g. 1 option is an imperative phrase ('Here is how to...') while 3 options are formal 3rd-person declarations.
        """
        opt_is_instruction = []
        for opt in options:
            t = opt.get("text", "")
            is_inst = any(pat.search(t) for pat in INSTRUCTIONAL_HEADING_PATTERNS)
            opt_is_instruction.append((opt.get("key"), is_inst))

        inst_count = sum(1 for _, is_inst in opt_is_instruction if is_inst)
        if inst_count == 1:
            leaked_key = next(k for k, is_inst in opt_is_instruction if is_inst)
            if leaked_key == correct_key:
                return True, "Correct option is structurally distinctive (instructional heading) compared to declarative distractors."
            else:
                return True, "Option structural imbalance: one distractor is an instructional heading while others are declarative."

        return False, None

    def validate_question(
        self,
        question_text: str,
        options: List[Dict[str, str]],
        correct_option: str,
        concept: Optional[str] = None,
        topic: Optional[str] = None,
        source_excerpt: Optional[str] = None,
        document_name: Optional[str] = None,
        page_number: Optional[int] = None,
        question_type: Optional[str] = "conceptual",
    ) -> ValidationResult:
        """
        Runs comprehensive validation across all quality criteria.
        Returns a ValidationResult object with is_valid, quality_score, and detailed diagnostics.
        """
        rejections = []
        notes = []

        # 1. Basic structural checks
        clean_q = (question_text or "").strip()
        if not clean_q or len(clean_q) < 20:
            rejections.append("Question stem is empty or too short (< 20 characters).")
        if any(clean_q.endswith(cutoff) for cutoff in ["...", ",", " and", " the", " of", " with", " in", " to", " for"]):
            rejections.append("Question stem is abruptly truncated or malformed.")
        if len(options) != 4:
            rejections.append(f"Expected exactly 4 options, got {len(options)}.")

        keys = [opt.get("key") for opt in options if isinstance(opt, dict)]
        if set(keys) != {"A", "B", "C", "D"}:
            rejections.append(f"Options must have keys A, B, C, D; got {keys}.")

        correct_opt_obj = next((opt for opt in options if isinstance(opt, dict) and opt.get("key") == correct_option), None)
        correct_text = correct_opt_obj.get("text", "").strip() if correct_opt_obj else ""

        if not correct_text:
            rejections.append(f"Correct option '{correct_option}' is missing or empty.")

        # 1b. Concept validity check
        if concept:
            clean_c = concept.strip().lower()
            if clean_c in GENERIC_CONCEPT_BLACKLIST or any(clean_c.startswith(prefix) for prefix in ["page ", "unit ", "chapter ", "section ", "example "]):
                rejections.append(f"Target concept '{concept}' is an invalid or generic document section header.")
            elif len(clean_c) < 3:
                rejections.append(f"Target concept '{concept}' is too short (< 3 characters).")

        has_bad_concept, bad_concept_msg = self.check_concept_naming_quality(concept, clean_q)
        if has_bad_concept and bad_concept_msg:
            rejections.append(bad_concept_msg)

        # 1c. Markdown table and parser artifact checks on question stem
        if "|" in clean_q:
            rejections.append("Question stem contains raw Markdown table syntax (|).")

        for pat in PARSER_GARBAGE_PATTERNS:
            if pat.search(clean_q):
                rejections.append(f"Question stem contains parser or code artifacts.")
                break

        for pat in PROMPT_LEAK_PATTERNS:
            if pat.search(clean_q):
                rejections.append(f"Question stem contains generation/prompt metadata.")
                break

        # 1d. Markdown table, parser artifacts, and format checks on options
        c_lower = (concept or "").lower()
        t_lower = (topic or "").lower()
        d_lower = (document_name or "").lower()
        s_lower = (source_excerpt or "").lower()
        all_ctx = f"{c_lower} {t_lower} {d_lower} {s_lower}"
        is_web_ruby = any(k in c_lower or k in t_lower for k in ["ruby", "web", "cgi", "rack", "webrick", "cookie", "tk", "gui"])
        is_crypto_sec = any(k in all_ctx for k in [
            "ssl", "tls", "crypto", "cipher", "security", "mac", "secret", "integrity",
            "auth", "encrypt", "rsa", "diffie", "hellman", "handshake", "certificate",
            "key exchange", "asymmetric", "symmetric", "hash"
        ])

        for opt in options:
            if not isinstance(opt, dict):
                rejections.append("Option item is not a structured dictionary.")
                continue
            opt_key = opt.get("key", "?")
            opt_text = (opt.get("text") or "").strip()

            if len(opt_text) < 4:
                rejections.append(f"Option '{opt_key}' is too short (< 4 characters).")
            if len(opt_text) > 250:
                rejections.append(f"Option '{opt_key}' is excessively long (> 250 characters), likely a raw chunk dump.")
            if "\n" in opt.get("text", ""):
                rejections.append(f"Option '{opt_key}' contains unparsed newlines.")
            if "|" in opt_text:
                rejections.append(f"Option '{opt_key}' contains raw Markdown table syntax (|).")

            for pat in PARSER_GARBAGE_PATTERNS:
                if pat.search(opt_text):
                    rejections.append(f"Option '{opt_key}' contains parser or code artifacts.")
                    break

            # Cross-domain contamination checks
            opt_lower = opt_text.lower()
            if not is_web_ruby:
                for bad_kw in ["cookie store", "procfile", "cgi script", "tkroot", "webrick"]:
                    if bad_kw in opt_lower:
                        rejections.append(f"Option '{opt_key}' contains unrelated cross-domain term '{bad_kw}'.")
                        break
            if not is_crypto_sec:
                for bad_kw in ["symmetric confidentiality", "cryptographic message authentication", "asymmetric key exchange", "unauthenticated client-side cookie stores"]:
                    if bad_kw in opt_lower:
                        rejections.append(f"Option '{opt_key}' contains unrelated security distractor '{bad_kw}'.")
                        break

        # 1e. Instructional heading / tutorial sentence answer check
        has_inst_ans, inst_ans_msg = self.check_instructional_or_heading_answer(correct_text)
        if has_inst_ans and inst_ans_msg:
            rejections.append(inst_ans_msg)

        # 1f. Semantic stem-answer compatibility check
        has_sem_incompat, sem_incompat_msg = self.check_semantic_stem_answer_compatibility(
            clean_q, correct_text, options, concept
        )
        if has_sem_incompat and sem_incompat_msg:
            rejections.append(sem_incompat_msg)

        # 1g. Code-token leakage / structural imbalance check
        has_code_leak, code_leak_msg = self.check_unusual_token_and_code_leakage(clean_q, options, correct_option)
        if has_code_leak and code_leak_msg:
            rejections.append(code_leak_msg)

        # 1h. Distractor structural balance check
        has_struct_imbal, struct_imbal_msg = self.check_distractor_structural_balance(options, correct_option)
        if has_struct_imbal and struct_imbal_msg:
            rejections.append(struct_imbal_msg)

        # 2. Direct verbatim leakage
        has_verbatim, verbatim_msg = self.check_verbatim_leakage(question_text, correct_text, options)
        if has_verbatim and verbatim_msg:
            rejections.append(verbatim_msg)

        # 3. N-gram phrase leakage (4-word phrases)
        has_ngram, ngram_msg = self.check_ngram_leakage(question_text, correct_text, concept=concept, n=self.min_ngram_leak_size)
        if has_ngram and ngram_msg:
            rejections.append(ngram_msg)

        # 4. Token overlap (non-concept words)
        overlap_ratio, is_excessive_overlap, overlap_msg = self.check_token_overlap(
            question_text, correct_text, concept=concept
        )
        if is_excessive_overlap and overlap_msg:
            rejections.append(overlap_msg)

        # 5. Citation metadata leakage into stem or options
        has_citation_leak, citation_msg = self.check_citation_leakage(question_text, document_name=document_name, options=options)
        if has_citation_leak and citation_msg:
            rejections.append(citation_msg)

        # 6. Source passage dumping into stem
        has_dump, dump_msg = self.check_source_dump(question_text, source_excerpt=source_excerpt)
        if has_dump and dump_msg:
            rejections.append(dump_msg)

        # 7. Option balance
        balance_score, balance_notes = self.check_option_balance(options, correct_option)
        notes.extend(balance_notes)
        if balance_score < 0.50:
            rejections.append(f"Option imbalance detected: {'; '.join(balance_notes)}")

        # 8. Compute quality & leakage scores
        leakage_score = 0.0
        if has_verbatim:
            leakage_score += 0.80
        if has_ngram:
            leakage_score += 0.40
        if has_citation_leak:
            leakage_score += 0.30
        if has_dump:
            leakage_score += 0.30
        leakage_score = min(1.0, leakage_score + (overlap_ratio * 0.40))

        # Base quality score starts at 1.0 and deducts penalties
        quality_score = 1.0
        if rejections:
            quality_score -= len(rejections) * 0.25
        quality_score -= (leakage_score * 0.40)
        quality_score *= balance_score

        # Reward varied question types
        valid_types = {
            "conceptual", "comparison", "application", "scenario",
            "reasoning", "trace_output", "interpretation", "edge_case", "complexity_analysis"
        }
        if question_type and question_type in valid_types:
            quality_score = min(1.0, quality_score + 0.05)
        else:
            notes.append(f"Question type '{question_type}' is unclassified or generic.")

        quality_score = max(0.0, min(1.0, round(quality_score, 3)))
        is_valid = (len(rejections) == 0) and (quality_score >= self.min_quality_threshold)

        return ValidationResult(
            is_valid=is_valid,
            quality_score=quality_score,
            leakage_score=round(leakage_score, 3),
            rejection_reasons=rejections,
            quality_notes=notes,
            details={
                "overlap_ratio": round(overlap_ratio, 3),
                "balance_score": round(balance_score, 3),
                "question_type": question_type,
            },
        )


# Global singleton instance
question_quality_validator = QuestionQualityValidator()


def validate_question(
    question_text: str,
    options: List[Dict[str, str]],
    correct_option: Optional[str] = None,
    correct_key: Optional[str] = None,
    concept: Optional[str] = None,
    concept_name: Optional[str] = None,
    topic: Optional[str] = None,
    source_excerpt: Optional[str] = None,
    source_chunk_text: Optional[str] = None,
    document_name: Optional[str] = None,
    page_number: Optional[int] = None,
    question_type: Optional[str] = "conceptual",
) -> ValidationResult:
    key = correct_option or correct_key or "A"
    c_name = concept or concept_name
    src = source_excerpt or source_chunk_text
    return question_quality_validator.validate_question(
        question_text=question_text,
        options=options,
        correct_option=key,
        concept=c_name,
        topic=topic,
        source_excerpt=src,
        document_name=document_name,
        page_number=page_number,
        question_type=question_type,
    )


def check_verbatim_leakage(stem: str, correct_text: str, options: Optional[List[Dict[str, str]]] = None) -> Tuple[bool, Optional[str]]:
    return question_quality_validator.check_verbatim_leakage(stem, correct_text, options or [])


def check_ngram_leakage(stem: str, correct_text: str, concept: Optional[str] = None, n: int = 4) -> Tuple[bool, Optional[str]]:
    return question_quality_validator.check_ngram_leakage(stem, correct_text, concept, n)


def check_token_overlap(stem: str, correct_text: str, concept_name: Optional[str] = None) -> float:
    ratio, _, _ = question_quality_validator.check_token_overlap(stem, correct_text, concept=concept_name)
    return ratio


def check_citation_leakage(
    stem: str,
    answer_or_doc: Optional[str] = None,
    document_name: Optional[str] = None,
    page_number: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    matches = []
    doc = document_name or (answer_or_doc if answer_or_doc and any(ext in answer_or_doc.lower() for ext in [".pdf", ".docx", ".pptx", ".txt"]) else None)
    if doc and doc.lower() in stem.lower() and len(doc) > 3:
        matches.append(doc)

    for pattern in CITATION_LEAK_PATTERNS:
        for m in pattern.finditer(stem):
            matches.append(m.group(0))
        if answer_or_doc:
            for m in pattern.finditer(answer_or_doc):
                matches.append(m.group(0))

    has_leak = len(matches) > 0
    return has_leak, matches


def check_source_dump(stem: str, source_chunk_text: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    return question_quality_validator.check_source_dump(stem, source_chunk_text)


def check_option_balance(options: List[Dict[str, str]], correct_key: str) -> Tuple[bool, Optional[str]]:
    score, notes = question_quality_validator.check_option_balance(options, correct_key)
    is_balanced = (score >= 0.85) and (len(notes) == 0)
    reason = "; ".join(notes) if notes else None
    return is_balanced, reason


def validate_mcq_production_gate(
    question_text: str,
    options: List[Dict[str, str]],
    correct_option: str,
    concept: Optional[str] = None,
    topic: Optional[str] = None,
    source_excerpt: Optional[str] = None,
    document_name: Optional[str] = None,
    page_number: Optional[int] = None,
    workspace_id: Optional[str] = None,
    question_type: Optional[str] = "conceptual",
) -> ValidationResult:
    """Authoritative production-grade MCQ validation gate satisfying all 15 LumoraAI quality criteria:

    1. Coherent question (length >= 20, proper ending punctuation, no broken cutoffs).
    2. Valid target concept/topic (not a generic document division header or artifact).
    3. Exactly 4 options with keys A, B, C, D.
    4. All options non-empty (length >= 4).
    5. Exactly one correct option in {A, B, C, D}.
    6. Correct answer matches one option and has substantive content.
    7. All distractors related to the SAME concept/domain (no cross-domain pollution).
    8. No unrelated chunks used as distractors (concise, <= 250 chars).
    9. No Markdown table garbage (|) in stem or options.
    10. No parser artifacts (code fences, shebangs, HTML, unparsed scripts).
    11. No citation metadata leakage (Page X, .pdf, .docx).
    12. No generation/prompt metadata exposed.
    13. Workspace-grounded.
    14. No cross-workspace contamination.
    15. Clean learner-facing strings (proper punctuation, no unescaped newlines).
    """
    return question_quality_validator.validate_question(
        question_text=question_text,
        options=options,
        correct_option=correct_option,
        concept=concept,
        topic=topic,
        source_excerpt=source_excerpt,
        document_name=document_name,
        page_number=page_number,
        question_type=question_type,
    )


def check_instructional_or_heading_answer(correct_text: str) -> Tuple[bool, Optional[str]]:
    return question_quality_validator.check_instructional_or_heading_answer(correct_text)


def check_concept_naming_quality(concept: Optional[str], stem: str) -> Tuple[bool, Optional[str]]:
    return question_quality_validator.check_concept_naming_quality(concept, stem)


def check_semantic_compatibility(stem: str, correct_text: str, options: List[Dict[str, str]], concept: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    return question_quality_validator.check_semantic_stem_answer_compatibility(stem, correct_text, options, concept)


