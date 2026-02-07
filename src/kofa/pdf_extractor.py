"""
PDF text extraction for KOFA decisions.

Downloads PDF from URL and extracts structured text with numbered paragraphs
and section detection. Works across all KOFA eras (2003-2026) and both
bokmål and nynorsk decisions.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

import httpx
import pymupdf

logger = logging.getLogger(__name__)

# Section keywords (bokmål + nynorsk)
SECTION_KEYWORDS = {
    "innledning": ["innledning", "innleiing"],
    "bakgrunn": ["bakgrunn"],
    "anfoersler": [
        "klagers anførsler",
        "innklagedes anførsler",
        "partenes anførsler",
        "klagar har i det vesentlege gjort gjeldande",
        "innklaga har i det vesentlege gjort gjeldande",
        "påstandsgrunnlag",
        "anførsler",
        "anførslar",
    ],
    "vurdering": [
        "klagenemndas vurdering",
        "klagenemnda si vurdering",
        "vurderinga til klagenemnda",
        "nemndas vurdering",
    ],
    "konklusjon": ["konklusjon"],
}


@dataclass
class DecisionParagraph:
    """A single numbered paragraph from a KOFA decision."""

    number: int
    text: str
    section: str = ""  # innledning, bakgrunn, anfoersler, vurdering, konklusjon


@dataclass
class DecisionText:
    """Structured text extracted from a KOFA decision PDF."""

    sak_nr: str
    paragraphs: list[DecisionParagraph] = field(default_factory=list)
    raw_text: str = ""
    conclusion: str = ""
    page_count: int = 0

    @property
    def paragraph_count(self) -> int:
        return len(self.paragraphs)

    @property
    def vurdering_paragraphs(self) -> list[DecisionParagraph]:
        """Get only the legal analysis paragraphs (the valuable part)."""
        return [p for p in self.paragraphs if p.section == "vurdering"]


# Regex to split on numbered paragraphs: (1), (2), etc.
# Handles both "(1)\n text" and "\n(1) text" formats across eras
PARAGRAPH_RE = re.compile(
    r"""
    (?:^|\n)\s*          # Start of text or newline
    \((\d+)\)            # Numbered paragraph marker
    \s+                  # Whitespace after marker
    """,
    re.VERBOSE,
)

# Pattern to find "Bakgrunn:" section start (skip header/summary)
BAKGRUNN_RE = re.compile(r"\nBakgrunn:\s*\n", re.IGNORECASE)

# Pattern to find "Konklusjon:" section
KONKLUSJON_RE = re.compile(r"\nKonklusjon:\s*\n", re.IGNORECASE)


class PdfExtractor:
    """Extract structured text from KOFA decision PDFs."""

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def extract_from_url(self, pdf_url: str, sak_nr: str) -> DecisionText:
        """Download PDF and extract structured text."""
        pdf_bytes = self._download(pdf_url)
        return self.extract_from_bytes(pdf_bytes, sak_nr)

    def extract_from_bytes(self, pdf_bytes: bytes, sak_nr: str) -> DecisionText:
        """Extract structured text from PDF bytes."""
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")

        full_text = ""
        for page in doc:
            full_text += page.get_text()

        page_count = doc.page_count
        doc.close()

        result = DecisionText(
            sak_nr=sak_nr,
            raw_text=full_text,
            page_count=page_count,
        )

        # Find where the actual decision body starts (after "Bakgrunn:")
        body_start = 0
        bakgrunn_match = BAKGRUNN_RE.search(full_text)
        if bakgrunn_match:
            body_start = bakgrunn_match.start()
        else:
            logger.warning(f"{sak_nr}: No 'Bakgrunn:' section found, parsing from start")

        body_text = full_text[body_start:]

        # Extract conclusion
        konklusjon_match = KONKLUSJON_RE.search(body_text)
        if konklusjon_match:
            result.conclusion = body_text[konklusjon_match.end():].strip()

        # Split into numbered paragraphs
        paragraphs = self._parse_paragraphs(body_text)
        if not paragraphs:
            logger.warning(f"{sak_nr}: No numbered paragraphs found")
            return result

        # Assign sections
        self._assign_sections(paragraphs, body_text)
        result.paragraphs = paragraphs

        return result

    def _download(self, pdf_url: str) -> bytes:
        """Download PDF to memory."""
        with httpx.Client(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "kofa-mcp/0.1.0"},
        ) as client:
            resp = client.get(pdf_url)
            resp.raise_for_status()
            return resp.content

    @staticmethod
    def _parse_paragraphs(text: str) -> list[DecisionParagraph]:
        """Split text into numbered paragraphs."""
        # Find all paragraph markers and their positions
        markers = list(PARAGRAPH_RE.finditer(text))
        if not markers:
            return []

        paragraphs = []
        seen_numbers = set()

        for i, match in enumerate(markers):
            num = int(match.group(1))

            # Skip duplicate (1)s from header — only take the first
            # occurrence of each number in sequence
            if num in seen_numbers and num == 1:
                # Reset: this is likely the start of a new section
                # (e.g. "Klagers anførsler" restarting at (1))
                # Only reset if last seen number was > 1
                if paragraphs and paragraphs[-1].number > 1:
                    seen_numbers.clear()
                else:
                    continue

            # Get text until next marker or end
            start = match.end()
            end = markers[i + 1].start() if i + 1 < len(markers) else len(text)
            para_text = text[start:end].strip()

            # Clean up common artifacts
            para_text = re.sub(r"\n\s+", "\n", para_text)

            if para_text:
                paragraphs.append(DecisionParagraph(number=num, text=para_text))
                seen_numbers.add(num)

        return paragraphs

    @staticmethod
    def _assign_sections(
        paragraphs: list[DecisionParagraph], full_text: str
    ) -> None:
        """Assign section labels to paragraphs based on section headings in text."""
        # Find section boundaries by searching for keywords in the full text
        section_positions: list[tuple[int, str]] = []

        for section_name, keywords in SECTION_KEYWORDS.items():
            for keyword in keywords:
                # Look for keyword as a standalone heading or inline marker
                pattern = re.compile(
                    rf"(?:^|\n)\s*{re.escape(keyword)}\s*:?\s*(?:\n|$)",
                    re.IGNORECASE,
                )
                for m in pattern.finditer(full_text):
                    section_positions.append((m.start(), section_name))

        # Sort by position in text
        section_positions.sort(key=lambda x: x[0])

        if not section_positions:
            # Default: everything is "bakgrunn" if no sections detected
            for p in paragraphs:
                p.section = "bakgrunn"
            return

        # Find paragraph positions in text to map them to sections
        para_positions = []
        for p in paragraphs:
            # Find this paragraph's text in the full text
            snippet = p.text[:50].replace("\n", " ")
            pos = full_text.find(snippet)
            if pos == -1:
                pos = full_text.find(p.text[:30])
            para_positions.append(pos if pos != -1 else 0)

        # Assign each paragraph to the most recent section before it
        for i, p in enumerate(paragraphs):
            p_pos = para_positions[i]
            assigned = ""
            for sec_pos, sec_name in section_positions:
                if sec_pos <= p_pos:
                    assigned = sec_name
                else:
                    break
            p.section = assigned or "bakgrunn"
