"""
PDF text extractor for Norwegian legislative preparatory works (forarbeider).

Extracts structured sections from Prop. L and NOU documents using PyMuPDF's
built-in TOC (Table of Contents) from embedded PDF bookmarks. Each TOC entry
becomes a section with extracted text content.

Supports 4 documents related to the Norwegian Public Procurement Act:
- Prop. 51 L (2015-2016): Original anskaffelsesloven
- Prop. 147 L (2024-2025): Amendments (samfunnshensyn)
- NOU 2023: 26: First part of procurement law reform
- NOU 2024: 9: Second part of procurement law reform
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

# Registry of known forarbeider PDFs: filename -> (doc_id, title, full_title, doc_type, session)
FORARBEIDER_REGISTRY: dict[str, tuple[str, str, str, str, str]] = {
    "prp201520160051000dddpdfs.pdf": (
        "prop-51-l-2015-2016",
        "Prop. 51 L (2015\u20132016)",
        "Prop. 51 L (2015\u20132016) Lov om offentlige anskaffelser (anskaffelsesloven)",
        "prop",
        "2015\u20132016",
    ),
    "prp202420250147000dddpdfs.pdf": (
        "prop-147-l-2024-2025",
        "Prop. 147 L (2024\u20132025)",
        "Prop. 147 L (2024\u20132025) Lov om endringer i anskaffelsesloven (samfunnshensyn mv.)",
        "prop",
        "2024\u20132025",
    ),
    "nou202320230026000dddpdfs.pdf": (
        "nou-2023-26",
        "NOU 2023: 26",
        "NOU 2023: 26 Ny lov om offentlige anskaffelser \u2013 f\u00f8rste delutredning",
        "nou",
        "2023",
    ),
    "nou202420240009000dddpdfs.pdf": (
        "nou-2024-9",
        "NOU 2024: 9",
        "NOU 2024: 9 Ny lov om offentlige anskaffelser \u2013 andre delutredning",
        "nou",
        "2024",
    ),
}

# Regex for extracting section numbers from TOC titles
_SECTION_NUMBER_RE = re.compile(r"^(Del\s+[IVX]+|Kapittel\s+\d+|Vedlegg\s+\d+|\d+(?:\.\d+)*)\s")

# Page header line: page number, document title, session - to be removed line-by-line
_HEADER_LINE_RE = re.compile(
    r"^[^\S\n]*("
    r"\d{1,4}"  # page number alone
    r"|(?:Prop\.\s+\d+\s+L|NOU\s+\d{4}:\s*\d+)"  # doc reference
    r"|(?:Lov\s+om\s+.*|Ny\s+lov\s+om\s+.*)"  # doc subtitle
    r"|\d{4}[\u2013-]\d{4}"  # session "2015-2016"
    r")[^\S\n]*$",
    re.MULTILINE,
)

# Soft hyphen character used in PDF text for line-break hyphens
_SOFT_HYPHEN = "\xad"


@dataclass
class ForarbeiderSection:
    """A single section extracted from a forarbeider document."""

    section_number: str
    title: str
    level: int
    page_start: int
    sort_order: int
    parent_path: str
    text: str = ""


@dataclass
class ForarbeiderDocument:
    """A complete forarbeider document with extracted sections."""

    doc_id: str
    title: str
    full_title: str
    doc_type: str
    session: str
    page_count: int
    source_file: str
    sections: list[ForarbeiderSection] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        """Total character count across all sections."""
        return sum(len(s.text) for s in self.sections)

    @property
    def section_count(self) -> int:
        """Number of sections in the document."""
        return len(self.sections)


def _extract_section_number(title: str, sort_order: int) -> str:
    """
    Extract section number from a TOC title.

    Handles patterns like:
    - "4.1.2 Nasjonal rett" -> "4.1.2"
    - "Del III Anskaffelsesprosessen" -> "Del III"
    - "Kapittel 15 Avvisning" -> "Kapittel 15"
    - "Vedlegg 1" -> "Vedlegg 1"
    - "1 Proposisjonens hovedinnhold" -> "1"
    - "Innledning" -> "s{sort_order}"
    """
    m = _SECTION_NUMBER_RE.match(title)
    if m:
        return m.group(1)
    return f"s{sort_order}"


def _build_parent_path(stack: list[tuple[int, str]], level: int, section_number: str) -> str:
    """
    Build hierarchical breadcrumb path from parent stack.

    Maintains a stack of (level, section_number) tuples. Pops entries
    until the top of stack has a lower level than current, then pushes
    the current entry.

    Returns path like "4 > 4.1 > 4.1.2".
    """
    # Pop entries at same or deeper level
    while stack and stack[-1][0] >= level:
        stack.pop()

    # Push current entry
    stack.append((level, section_number))

    # Build path from all entries in stack
    return " > ".join(s[1] for s in stack)


def _clean_page_text(text: str) -> str:
    """Remove page headers/footers and clean up whitespace artifacts."""
    # Remove soft hyphens (used for line-break hyphenation in PDFs)
    text = text.replace(_SOFT_HYPHEN + "\n", "")

    # Remove header lines (page numbers, doc titles, sessions) that appear
    # at the top of each page. Only remove from the first ~6 non-empty lines
    # to avoid stripping actual content that happens to match.
    lines = text.split("\n")
    non_empty_seen = 0
    cleaned_lines: list[str] = []
    for line in lines:
        if non_empty_seen < 6 and line.strip():
            non_empty_seen += 1
            if _HEADER_LINE_RE.match(line):
                continue  # Skip header line
        cleaned_lines.append(line)

    text = "\n".join(cleaned_lines)

    # Collapse excessive whitespace-only lines at start
    text = re.sub(r"^(?:[^\S\n]*\n){3,}", "\n", text)

    return text


def _find_heading_in_text(page_text: str, title: str) -> tuple[int, int]:
    """
    Find a TOC heading in page text and return (start, end) positions.

    PDF text has section numbers on separate lines from their title text,
    e.g., TOC title "2.1 Revisjon av nasjonal rett" appears in PDF as:
        2.1 \\n
        Revisjon av nasjonal rett \\n

    Returns (start_of_heading, end_of_heading) or (-1, -1) if not found.
    The heading includes the section number line and the title line(s).
    """
    # Strategy 1: Direct substring match (works for short/simple titles)
    pos = page_text.find(title)
    if pos >= 0:
        end = pos + len(title)
        # Skip trailing whitespace and newline
        while end < len(page_text) and page_text[end] in " \t":
            end += 1
        if end < len(page_text) and page_text[end] == "\n":
            end += 1
        return (pos, end)

    # Strategy 2: For numbered sections like "2.1.2 Title text",
    # the number may appear on its own line ("2.1.2\nTitle text\n")
    # or on the same line with extra whitespace ("2.1.2  Title text\n")
    m = _SECTION_NUMBER_RE.match(title)
    if m:
        sec_num = m.group(1)
        title_text = title[m.end() :].strip()

        # Search for section number at start of line, followed by either
        # a newline (number alone) or whitespace + text (number + title)
        num_pattern = re.compile(
            r"(?:^|\n)" + re.escape(sec_num) + r"[^\S\n]*(?:\n|[^\S\n]+\S)",
        )
        num_match = num_pattern.search(page_text)
        if num_match:
            heading_start = num_match.start()
            if heading_start > 0 and page_text[heading_start] == "\n":
                heading_start += 1  # Don't include the preceding \n

            # The heading end is after the title text line(s).
            # Title text may span multiple lines in the PDF, so we need
            # to consume lines until we've matched the last word.
            after_num = num_match.end()
            if title_text:
                title_words = title_text.split()
                last_word = title_words[-1]
                # Search for the last word of the title near the number
                search_region = page_text[after_num : after_num + 300]
                last_word_pos = search_region.find(last_word)
                if last_word_pos >= 0:
                    abs_pos = after_num + last_word_pos + len(last_word)
                    # Skip to end of line
                    while abs_pos < len(page_text) and page_text[abs_pos] in " \t":
                        abs_pos += 1
                    if abs_pos < len(page_text) and page_text[abs_pos] == "\n":
                        abs_pos += 1
                    return (heading_start, abs_pos)
                # Fallback: use first word
                first_word = title_words[0]
                word_pos = page_text.find(first_word, after_num)
                if word_pos >= 0 and word_pos - after_num < 50:
                    line_end = page_text.find("\n", word_pos)
                    if line_end < 0:
                        line_end = len(page_text)
                    else:
                        line_end += 1
                    return (heading_start, line_end)
            return (heading_start, after_num)

    # Strategy 3: For "Kapittel N" — appears literally, sometimes duplicated
    if title.startswith("Kapittel "):
        # Find last occurrence (first is often a repeated header)
        last_pos = -1
        search_start = 0
        while True:
            pos = page_text.find(title, search_start)
            if pos < 0:
                break
            last_pos = pos
            search_start = pos + 1
        if last_pos >= 0:
            end = last_pos + len(title)
            while end < len(page_text) and page_text[end] in " \t":
                end += 1
            if end < len(page_text) and page_text[end] == "\n":
                end += 1
            return (last_pos, end)

    # Strategy 4: Try just the title text (without number prefix)
    # for cases where the number is stripped by header cleaning
    if m:
        title_text = title[m.end() :].strip()
        if title_text and len(title_text) > 5:
            pos = page_text.find(title_text)
            if pos >= 0:
                end = pos + len(title_text)
                while end < len(page_text) and page_text[end] in " \t":
                    end += 1
                if end < len(page_text) and page_text[end] == "\n":
                    end += 1
                return (pos, end)

    # Strategy 5: First few words of the title
    words = title.split()
    if len(words) >= 2:
        fragment = " ".join(words[:2])
        pos = page_text.find(fragment)
        if pos >= 0:
            end = pos + len(fragment)
            while end < len(page_text) and page_text[end] in " \t":
                end += 1
            if end < len(page_text) and page_text[end] == "\n":
                end += 1
            return (pos, end)

    return (-1, -1)


class ForarbeiderExtractor:
    """Extract structured text from forarbeider PDFs using embedded TOC."""

    def extract(self, pdf_path: str | Path) -> ForarbeiderDocument:
        """
        Extract all sections from a forarbeider PDF.

        Reads the PDF's embedded Table of Contents and extracts text
        for each section by splitting on TOC page boundaries and
        title markers within pages.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            ForarbeiderDocument with all sections populated.

        Raises:
            ValueError: If the PDF filename is not in FORARBEIDER_REGISTRY.
            FileNotFoundError: If the PDF file does not exist.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        filename = pdf_path.name
        if filename not in FORARBEIDER_REGISTRY:
            raise ValueError(
                f"Unknown forarbeider PDF: {filename}. "
                f"Known files: {', '.join(FORARBEIDER_REGISTRY.keys())}"
            )

        doc_id, title, full_title, doc_type, session = FORARBEIDER_REGISTRY[filename]

        doc = pymupdf.open(str(pdf_path))
        try:
            toc = doc.get_toc()
            if not toc:
                logger.warning(f"{filename}: No TOC found in PDF")
                return ForarbeiderDocument(
                    doc_id=doc_id,
                    title=title,
                    full_title=full_title,
                    doc_type=doc_type,
                    session=session,
                    page_count=doc.page_count,
                    source_file=filename,
                )

            logger.info(f"{filename}: {len(toc)} TOC entries, {doc.page_count} pages")

            # Cache page texts (0-indexed)
            page_texts: dict[int, str] = {}

            sections = self._build_sections(doc, toc, page_texts)

            result = ForarbeiderDocument(
                doc_id=doc_id,
                title=title,
                full_title=full_title,
                doc_type=doc_type,
                session=session,
                page_count=doc.page_count,
                source_file=filename,
                sections=sections,
            )

            non_empty = sum(1 for s in sections if s.text.strip())
            logger.info(
                f"{filename}: {len(sections)} sections extracted, "
                f"{non_empty} non-empty, {result.char_count} total chars"
            )

            return result
        finally:
            doc.close()

    def _build_sections(
        self,
        doc: pymupdf.Document,
        toc: list[list],
        page_texts: dict[int, str],
    ) -> list[ForarbeiderSection]:
        """Build section list from TOC entries with extracted text."""
        sections: list[ForarbeiderSection] = []
        parent_stack: list[tuple[int, str]] = []

        for i, entry in enumerate(toc):
            level, title, page_num = entry[0], entry[1], entry[2]

            section_number = _extract_section_number(title, sort_order=i)
            parent_path = _build_parent_path(parent_stack, level, section_number)

            # Determine text boundaries
            next_entry = toc[i + 1] if i + 1 < len(toc) else None
            text = self._extract_section_text(doc, page_texts, title, page_num, next_entry)

            sections.append(
                ForarbeiderSection(
                    section_number=section_number,
                    title=title,
                    level=level,
                    page_start=page_num,
                    sort_order=i,
                    parent_path=parent_path,
                    text=text,
                )
            )

        return sections

    def _get_page_text(
        self,
        doc: pymupdf.Document,
        page_texts: dict[int, str],
        page_idx: int,
    ) -> str:
        """Get cleaned text for a page (0-indexed), with caching."""
        if page_idx not in page_texts:
            if 0 <= page_idx < doc.page_count:
                raw = str(doc[page_idx].get_text())
                page_texts[page_idx] = _clean_page_text(raw)
            else:
                page_texts[page_idx] = ""
        return page_texts[page_idx]

    def _extract_section_text(
        self,
        doc: pymupdf.Document,
        page_texts: dict[int, str],
        title: str,
        page_num: int,
        next_entry: list | None,
    ) -> str:
        """
        Extract text content for a single section.

        Uses the current section's page/title and the next section's
        page/title to determine text boundaries.
        """
        # TOC pages are 1-indexed, convert to 0-indexed
        start_page_idx = page_num - 1

        if next_entry is None:
            # Last section: extract to end of document
            end_page_idx = doc.page_count - 1
            next_title = None
            next_page_idx = end_page_idx + 1
        else:
            next_title = next_entry[1]
            next_page_idx = next_entry[2] - 1
            end_page_idx = next_page_idx

        # Collect text from all pages in range
        text_parts: list[str] = []
        for page_idx in range(start_page_idx, min(end_page_idx + 1, doc.page_count)):
            page_text = self._get_page_text(doc, page_texts, page_idx)

            if page_idx == start_page_idx:
                # On start page: find current heading and take text after it
                _, heading_end = _find_heading_in_text(page_text, title)
                if heading_end >= 0:
                    page_text = page_text[heading_end:]

            if page_idx == next_page_idx and next_title is not None:
                # On end page: take text before next heading
                heading_start, _ = _find_heading_in_text(page_text, next_title)
                if heading_start >= 0:
                    page_text = page_text[:heading_start]

            text_parts.append(page_text)

        text = "\n".join(text_parts)

        # Final cleanup
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def extract_all(pdf_dir: str | Path) -> list[ForarbeiderDocument]:
    """
    Extract all forarbeider documents from a directory.

    Looks for known PDF filenames in the given directory and extracts
    each one found.

    Args:
        pdf_dir: Directory containing forarbeider PDFs.

    Returns:
        List of extracted documents.
    """
    pdf_dir = Path(pdf_dir)
    extractor = ForarbeiderExtractor()
    documents: list[ForarbeiderDocument] = []

    for filename in sorted(FORARBEIDER_REGISTRY.keys()):
        pdf_path = pdf_dir / filename
        if pdf_path.exists():
            try:
                doc = extractor.extract(pdf_path)
                documents.append(doc)
                logger.info(f"Extracted {doc.title}: {doc.section_count} sections")
            except Exception:
                logger.exception(f"Failed to extract {filename}")
        else:
            logger.warning(f"PDF not found: {pdf_path}")

    return documents
