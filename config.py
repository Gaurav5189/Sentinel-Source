"""
Sentinel-Source — Centralized Configuration Module.

All environment variables, constants, and default values are loaded here once.
Other modules should import from this module instead of calling load_dotenv() 
or os.environ.get() individually.
"""

import os
import re
import logging
from dotenv import load_dotenv

# ──────────────────────────────────────────────
# Load .env once at application startup
# ──────────────────────────────────────────────
load_dotenv()

# ──────────────────────────────────────────────
# Logging Configuration
# ──────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_LEVEL = logging.INFO

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for structured, module-level logging."""
    return logging.getLogger(name)


# ──────────────────────────────────────────────
# API Keys & Credentials
# ──────────────────────────────────────────────
OPENROUTER_API_KEY: str | None = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL: str | None = os.environ.get("OPENROUTER_MODEL")
GITHUB_TOKEN: str | None = os.environ.get("GITHUB_TOKEN")
GITLAB_TOKEN: str | None = os.environ.get("GITLAB_TOKEN")

# ──────────────────────────────────────────────
# API Base URLs
# ──────────────────────────────────────────────
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
GITHUB_API_URL = "https://api.github.com"
GITLAB_API_URL = "https://gitlab.com/api/v4"

# ──────────────────────────────────────────────
# Timeouts (seconds)
# ──────────────────────────────────────────────
DEFAULT_TIMEOUT = 15
LLM_TIMEOUT = 90
GITLAB_TIMEOUT = 30
README_FETCH_TIMEOUT = 5

# ──────────────────────────────────────────────
# Processing Limits
# ──────────────────────────────────────────────
MAX_README_LENGTH = 2000
TOP_RESULTS_DISPLAY = 6
MAX_THREAD_WORKERS = 10
GITLAB_MAX_RETRIES = 2
MAX_QUERY_LENGTH = 200

# ──────────────────────────────────────────────
# Allowed Domains for README Fetching (SSRF Defense)
# ──────────────────────────────────────────────
ALLOWED_README_DOMAINS = frozenset([
    "raw.githubusercontent.com",
    "gitlab.com",
])

# ──────────────────────────────────────────────
# Utility Functions
# ──────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for safe use as a filename.
    Removes any character that isn't alphanumeric, dash, or underscore.
    """
    return re.sub(r'[^\w\-]', '_', name)


def sanitize_readme_text(text: str, max_length: int = MAX_README_LENGTH) -> str:
    """
    Sanitize README content before sending to LLM to mitigate prompt injection.
    - Strips control characters (except newlines/tabs)
    - Truncates to max_length
    """
    if not text:
        return ""
    
    # Remove control characters except newline and tab
    cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Truncate to max length
    cleaned = cleaned[:max_length]
    
    return cleaned


def validate_url_domain(url: str, allowed_domains: frozenset = ALLOWED_README_DOMAINS) -> bool:
    """
    Validate that a URL belongs to one of the allowed domains.
    Prevents SSRF by ensuring we only fetch from trusted sources.
    """
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.hostname in allowed_domains and parsed.scheme == "https"
    except Exception:
        return False


def sanitize_query(query: str) -> str:
    """
    Sanitize and validate user search query input.
    - Strips whitespace
    - Enforces max length
    - Removes null bytes and control characters
    """
    if not query:
        return ""
    
    # Remove null bytes and control characters
    cleaned = re.sub(r'[\x00-\x1f\x7f]', '', query)
    
    # Strip and enforce max length
    cleaned = cleaned.strip()[:MAX_QUERY_LENGTH]
    
    return cleaned
