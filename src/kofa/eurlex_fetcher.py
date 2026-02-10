"""
EUR-Lex fetcher for EU Court judgments referenced in KOFA decisions.

Fetches full-text judgments from EUR-Lex HTML, extracts metadata from
<meta> tags and body text. Handles both old (pre-~2012) and new HTML formats.

EUR-Lex content is CC BY 4.0 licensed. robots.txt allows crawling with
reasonable delay (we use 10s between requests).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

logger = logging.getLogger(__name__)

# EUR-Lex base URL for HTML judgments
EURLEX_HTML_URL = "https://eur-lex.europa.eu/legal-content/{lang}/TXT/HTML/?uri=CELEX:{celex}"


@dataclass
class EUJudgment:
    """Parsed EU Court judgment from EUR-Lex."""

    eu_case_id: str  # "C-19/00"
    celex: str  # "62000CJ0019"
    case_name: str  # from DC.description
    judgment_date: str | None  # "2001-10-18"
    subject: str  # from DC.subject
    description: str  # from DC.description (parties, court, topic)
    full_text: str  # extracted plain text
    source_url: str
    language: str  # "EN"


def case_id_to_celex(case_id: str) -> str:
    """
    Convert EU case ID to CELEX number.

    C-19/00  → 62000CJ0019
    C-454/06 → 62006CJ0454
    T-345/03 → 62003TJ0345

    Format: 6{year}{court}{case_number}
    - Court: CJ = Court of Justice (C-), TJ = General Court (T-)
    - Year: 4 digits
    - Case number: zero-padded to 4 digits
    """
    case_id = case_id.strip()
    m = re.match(r"([CT])-(\d+)/(\d+)", case_id)
    if not m:
        raise ValueError(f"Invalid EU case ID format: {case_id}")

    court_letter = m.group(1)
    case_num = int(m.group(2))
    year_short = m.group(3)

    # Expand 2-digit year to 4-digit
    if len(year_short) == 2:
        y = int(year_short)
        year = 2000 + y if y < 50 else 1900 + y
    else:
        year = int(year_short)

    court = "CJ" if court_letter == "C" else "TJ"
    return f"6{year}{court}{case_num:04d}"


class _MetaTagParser(HTMLParser):
    """Extract <meta name="DC.*"> content from HTML head."""

    def __init__(self):
        super().__init__()
        self.meta: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return
        attr_dict = dict(attrs)
        name = attr_dict.get("name", "")
        content = attr_dict.get("content", "")
        if name and content:
            self.meta[name] = content


def _extract_meta_tags(html: str) -> dict[str, str]:
    """Extract Dublin Core metadata from HTML <meta> tags."""
    parser = _MetaTagParser()
    # Only parse head section for speed
    head_end = html.find("</head>")
    parser.feed(html[: head_end + 7] if head_end != -1 else html[:5000])
    return parser.meta


# Patterns for stripping nav chrome from EUR-Lex pages
_STRIP_PATTERNS = [
    re.compile(r"^.*?(?=JUDGMENT OF THE COURT|JUDGMENT OF THE GENERAL COURT)", re.DOTALL),
    re.compile(r"Help\s+Print this page.*?(?=\n\n)", re.DOTALL),
]


def _extract_text_from_html(html: str) -> str:
    """
    Extract clean plain text from EUR-Lex judgment HTML.

    Handles two formats:
    - Old (pre-~2012): <div id="TexteOnly"> with <h2> sections
    - New (post-~2012): CSS classes without TexteOnly wrapper

    Strategy:
    1. Look for <div id="TexteOnly"> — use if found
    2. Otherwise extract from <body>
    3. Strip navigation/chrome
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Remove script and style elements
    for tag in soup.find_all(["script", "style", "nav"]):
        tag.decompose()

    # Try old format first
    texte_only = soup.find("div", id="TexteOnly")
    if texte_only:
        text = texte_only.get_text(separator="\n", strip=True)
    else:
        # New format: extract from body
        body = soup.find("body")
        if body:
            text = body.get_text(separator="\n", strip=True)
        else:
            text = soup.get_text(separator="\n", strip=True)

    # Strip leading chrome (everything before JUDGMENT OF THE COURT)
    for pattern in _STRIP_PATTERNS:
        text = pattern.sub("", text)

    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


class EurLexFetcher:
    """Fetch and parse EU Court judgments from EUR-Lex."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def fetch(self, eu_case_id: str, language: str = "EN") -> EUJudgment | None:
        """
        Fetch and parse a single EU Court judgment.

        Returns None on 404. Raises on other HTTP errors.
        """
        try:
            celex = case_id_to_celex(eu_case_id)
        except ValueError as e:
            logger.warning(f"Cannot convert case ID '{eu_case_id}': {e}")
            return None

        url = EURLEX_HTML_URL.format(lang=language, celex=celex)

        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "kofa-mcp/0.1.0 (Norwegian procurement law research)"},
        ) as client:
            try:
                resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    if language == "EN":
                        logger.info(f"{eu_case_id}: No English version, trying French")
                        return self.fetch(eu_case_id, language="FR")
                    logger.warning(f"{eu_case_id}: Not found on EUR-Lex ({language})")
                    return None
                raise

            html = resp.text

        # Extract metadata from <meta> tags
        meta = _extract_meta_tags(html)

        # Extract plain text from HTML body
        full_text = _extract_text_from_html(html)

        if not full_text or len(full_text) < 100:
            logger.warning(f"{eu_case_id}: Extracted text too short ({len(full_text)} chars)")
            return None

        # Parse judgment date from DC.date or DC.date.created
        judgment_date = meta.get("DC.date") or meta.get("DC.date.created")

        return EUJudgment(
            eu_case_id=eu_case_id,
            celex=celex,
            case_name=meta.get("DC.description", ""),
            judgment_date=judgment_date,
            subject=meta.get("DC.subject", ""),
            description=meta.get("DC.description", ""),
            full_text=full_text,
            source_url=url,
            language=language,
        )
