import re
from typing import Optional, List

_SECRET_PATTERNS = [
    re.compile(r"(AIza[0-9A-Za-z-_]{15,})"),                      # Google Gemini / Maps keys
    re.compile(r"(sk-[a-zA-Z0-9_\-]{15,})"),                     # OpenAI keys / generic sk- keys
    re.compile(r"(gsk_[a-zA-Z0-9_\-]{15,})"),                    # Groq keys
    re.compile(r"(Bearer\s+)([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),  # Bearer tokens
    re.compile(r"(api[_-]?key[\"\'\s:=]+)([a-zA-Z0-9_\-]{15,})", re.IGNORECASE),
    re.compile(r"(authorization[\"\'\s:=]+)([a-zA-Z0-9_\-\.]{15,})", re.IGNORECASE),
]


def mask_secret_string(secret: Optional[str]) -> str:
    """Masks a secret string showing only the first 3 and last 3 characters."""
    if not secret:
        return "None"
    s = str(secret).strip()
    if len(s) <= 8:
        return "***"
    return f"{s[:3]}...{s[-3:]}"


def sanitize_text(text: Optional[str], known_secrets: Optional[List[str]] = None) -> str:
    """
    Scrubs regex secret patterns and explicitly known secret values from any text or log message.
    """
    if not text:
        return ""
    sanitized = str(text)

    # 1. Scrub explicitly known secrets
    if known_secrets:
        for secret in known_secrets:
            if secret and len(secret) >= 6:
                sanitized = sanitized.replace(secret, mask_secret_string(secret))

    # 2. Scrub regex patterns
    for pat in _SECRET_PATTERNS:
        def _replace_match(m):
            if len(m.groups()) == 1:
                return mask_secret_string(m.group(1))
            elif len(m.groups()) == 2:
                return f"{m.group(1)}{mask_secret_string(m.group(2))}"
            return "***"

        sanitized = pat.sub(_replace_match, sanitized)

    return sanitized
