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


# Joined cases: EUR-Lex publishes the judgment under the primary (lowest) case number.
# Maps secondary case ID → primary case ID for cases referenced in KOFA/forarbeider.
_JOINED_CASE_MAP: dict[str, str] = {
    "C-34/03": "C-21/03",  # Fabricom
    "C-260/99": "C-223/99",  # Agorà/Excelsior
    "C-286/99": "C-285/99",  # Impresa Lombardini
    "C-28/01": "C-20/01",  # Commission v Germany
    "C-149/08": "C-145/08",  # Club Hotel Loutraki
    "C-156/19": "C-155/19",  # FIGC
    "C-161/12": "C-159/12",  # Venturini
    "C-183/11": "C-182/11",  # Econord
    "C-228/04": "C-226/04",  # La Cascina
    "C-275/21": "C-274/21",  # EPIC Financial Consulting
    "C-384/21": "C-383/21",  # Sambre & Biesme
    "C-443/22": "C-441/22",  # Obshtina Razgrad
    "C-463/03": "C-462/03",  # Strabag/Kostmann
    "C-48/93": "C-46/93",  # Brasserie du Pêcheur
    "C-203/11": "C-197/11",  # Libert v Gouvernement flamand
    "C-601/20": "C-37/20",  # WM/Sovim v Luxembourg
    "C-722/19": "C-721/19",  # Sisal/Magellan Robotech
    "C-84/21": "C-68/21",  # Iveco Orecchia
    "C-91/19": "C-89/19",  # Rieco (Order, joined C-89/19 to C-91/19)
}


def case_id_to_celex(case_id: str, doc_type: str = "CJ") -> str:
    """
    Convert EU case ID to CELEX number.

    C-19/00  → 62000CJ0019
    C-454/06 → 62006CJ0454
    T-345/03 → 62003TJ0345

    Format: 6{year}{court}{case_number}
    - Court: CJ = Court of Justice (C-), TJ = General Court (T-)
    - Year: 4 digits
    - Case number: zero-padded to 4 digits

    doc_type overrides the court suffix (e.g. "CO" for Orders).
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

    if doc_type != "CJ":
        court = doc_type
    elif court_letter == "C":
        court = "CJ"
    else:
        court = "TJ"
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

        Handles three failure modes:
        1. Joined cases — redirects to primary case via _JOINED_CASE_MAP
        2. Orders (CO) — retries with CO suffix when CJ returns 404
        3. Language fallback — tries French when English returns 404

        Returns None on 404. Raises on other HTTP errors.
        """
        # Resolve joined cases: fetch under primary case ID
        primary_id = _JOINED_CASE_MAP.get(eu_case_id)
        if primary_id:
            logger.info(f"{eu_case_id}: Joined case, fetching under {primary_id}")
            result = self.fetch(primary_id, language=language)
            if result:
                # Store under the original case ID so the caller gets the right reference
                result.eu_case_id = eu_case_id
            return result

        try:
            celex = case_id_to_celex(eu_case_id)
        except ValueError as e:
            logger.warning(f"Cannot convert case ID '{eu_case_id}': {e}")
            return None

        result = self._fetch_celex(eu_case_id, celex, language)
        if result:
            return result

        # CJ not found — try CO (Order) before giving up
        try:
            celex_co = case_id_to_celex(eu_case_id, doc_type="CO")
        except ValueError:
            return None

        logger.info(f"{eu_case_id}: CJ not found, trying CO (Order)")
        return self._fetch_celex(eu_case_id, celex_co, language)

    def _fetch_celex(self, eu_case_id: str, celex: str, language: str = "EN") -> EUJudgment | None:
        """Fetch a specific CELEX document from EUR-Lex."""
        url = EURLEX_HTML_URL.format(lang=language, celex=celex)

        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "kofa-mcp/0.1.0 (Norwegian procurement law research)"},
        ) as client:
            try:
                resp = client.get(url)
                # EUR-Lex returns 202 Accepted when content is being generated
                # Retry once after a pause
                if resp.status_code == 202:
                    import time

                    logger.info(f"{eu_case_id}: EUR-Lex returned 202, retrying in 15s...")
                    time.sleep(15)
                    resp = client.get(url)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    if language == "EN":
                        logger.info(f"{eu_case_id}: No English version, trying French")
                        return self._fetch_celex(eu_case_id, celex, language="FR")
                    logger.debug(f"{eu_case_id}: Not found ({celex}, {language})")
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
