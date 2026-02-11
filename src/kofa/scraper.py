"""
HTML scraper for KOFA case metadata.

Extracts structured metadata from case pages at klagenemndssekretariatet.no.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Date format used on KOFA pages: DD.MM.YYYY
DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


@dataclass
class CaseMetadata:
    """Structured metadata extracted from a KOFA case page."""

    innklaget: str | None = None
    klager: str | None = None
    sakstype: str | None = None
    avgjoerelse: str | None = None
    saken_gjelder: str | None = None
    regelverk: str | None = None
    konkurranseform: str | None = None
    prosedyre: str | None = None
    saksbehandler: str | None = None
    saksnummer: str | None = None
    avsluttet_dato: str | None = None
    pdf_url: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


# Label → CaseMetadata field name mapping
LABEL_MAP: dict[str, str] = {
    "innklaget": "innklaget",
    "innklagede": "innklaget",
    "klager": "klager",
    "type sak": "sakstype",
    "sakstype": "sakstype",
    "avgjørelse": "avgjoerelse",
    "avgjort": "avgjoerelse",
    "saken gjelder": "saken_gjelder",
    "regelverk": "regelverk",
    "konkurranseform": "konkurranseform",
    "prosedyre": "prosedyre",
    "saksbehandler": "saksbehandler",
    "saksnummer": "saksnummer",
    "avsluttet": "avsluttet_dato",
}


def _parse_date(text: str) -> str | None:
    """Parse DD.MM.YYYY to ISO date string."""
    m = DATE_RE.search(text)
    if not m:
        return None
    try:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except (ValueError, OverflowError):
        return None


def _normalize_label(label: str) -> str:
    """Normalize a metadata label for lookup."""
    return label.strip().rstrip(":").lower()


class KofaScraper:
    """Scrapes KOFA case pages for structured metadata."""

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={"User-Agent": "kofa-mcp/0.1.0"},
        )

    def extract_metadata(self, url: str) -> CaseMetadata:
        """
        Extract metadata from a KOFA case page.

        Args:
            url: Full URL to the case page

        Returns:
            CaseMetadata with extracted fields
        """
        response = self.client.get(url)
        response.raise_for_status()
        return self.parse_html(response.text, url)

    def parse_html(self, html: str, base_url: str = "") -> CaseMetadata:
        """
        Parse HTML and extract case metadata.

        Tries three strategies:
        1. <strong>Label:</strong> Value pattern (most common)
        2. <dl>/<dt>/<dd> definition lists
        3. <table> rows
        """
        soup = BeautifulSoup(html, "lxml")
        meta = CaseMetadata()

        # Find the main content area
        content = soup.find("div", class_="entry-content") or soup.find("article") or soup

        # Strategy 1: <strong>Label:</strong> Value
        self._extract_strong_labels(content, meta)

        # Strategy 2: <dl> definition lists
        self._extract_dl(content, meta)

        # Strategy 3: <table> rows
        self._extract_table(content, meta)

        # Extract PDF link
        self._extract_pdf_link(content, meta, base_url)

        # Parse date fields
        if meta.avsluttet_dato and not re.match(r"\d{4}-\d{2}-\d{2}", meta.avsluttet_dato):
            parsed = _parse_date(meta.avsluttet_dato)
            if parsed:
                meta.avsluttet_dato = parsed

        return meta

    def _extract_strong_labels(self, soup: BeautifulSoup | Tag, meta: CaseMetadata) -> None:
        """Extract from <strong>Label:</strong> Value pattern."""
        for strong in soup.find_all("strong"):
            text = strong.get_text(strip=True)
            if not text or ":" not in text:
                continue

            label = _normalize_label(text)
            field_name = LABEL_MAP.get(label)
            if not field_name:
                continue

            # Get text after the <strong> tag
            next_sibling = strong.next_sibling
            value = ""
            if next_sibling:
                if hasattr(next_sibling, "get_text"):
                    value = next_sibling.get_text(strip=True)
                else:
                    value = str(next_sibling).strip()

            # Clean up leading colon/whitespace
            value = value.lstrip(":").strip()

            if value and not getattr(meta, field_name):
                setattr(meta, field_name, value)

    def _extract_dl(self, soup: BeautifulSoup | Tag, meta: CaseMetadata) -> None:
        """Extract from <dl>/<dt>/<dd> definition lists."""
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds, strict=False):
                label = _normalize_label(dt.get_text(strip=True))
                field_name = LABEL_MAP.get(label)
                if field_name and not getattr(meta, field_name):
                    setattr(meta, field_name, dd.get_text(strip=True))

    def _extract_table(self, soup: BeautifulSoup | Tag, meta: CaseMetadata) -> None:
        """Extract from <table> rows with label/value columns."""
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) >= 2:
                    label = _normalize_label(cells[0].get_text(strip=True))
                    field_name = LABEL_MAP.get(label)
                    if field_name and not getattr(meta, field_name):
                        setattr(meta, field_name, cells[1].get_text(strip=True))

    def _extract_pdf_link(
        self, soup: BeautifulSoup | Tag, meta: CaseMetadata, base_url: str
    ) -> None:
        """Find PDF link in the page."""
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if href.endswith(".pdf") and "avgjorelse" in href.lower():
                meta.pdf_url = href
                return
            if href.endswith(".pdf") and "klagenemnd" in href.lower():
                meta.pdf_url = href
                return
        # Fallback: any PDF link
        for a in soup.find_all("a", href=True):
            href = str(a["href"])
            if href.endswith(".pdf"):
                meta.pdf_url = href
                return

    def close(self):
        """Close the HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
