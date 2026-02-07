"""
Reference extraction from KOFA decision text.

Extracts law references (anskaffelsesloven, anskaffelsesforskriften, etc.)
and KOFA cross-references (sak 2019/491) from structured decision paragraphs.

Scope: Designed for 2020+ cases using current anskaffelsesloven (2016)
and anskaffelsesforskriften (2016).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# =============================================================================
# Data classes
# =============================================================================


@dataclass
class LawReference:
    """A reference to a law or regulation section."""

    law_name: str          # Normalized name (e.g. "anskaffelsesforskriften")
    section: str           # Section number (e.g. "2-4", "12")
    raw_text: str          # Original matched text
    reference_type: str    # "lov" or "forskrift"
    position: int          # Character position in text


@dataclass
class CaseReference:
    """A reference to another KOFA case."""

    sak_nr: str            # e.g. "2019/491"
    raw_text: str
    position: int


# =============================================================================
# Law name normalization
# =============================================================================

# Maps various names/aliases to canonical names
LAW_ALIASES: dict[str, str] = {
    # Default bare forms in KOFA context
    "forskriften": "anskaffelsesforskriften",
    "loven": "anskaffelsesloven",
    # Common abbreviations
    "foa": "anskaffelsesforskriften",
    "loa": "anskaffelsesloven",
    # Full names -> canonical
    "anskaffelsesforskriften": "anskaffelsesforskriften",
    "anskaffelsesloven": "anskaffelsesloven",
    "anskaffelseslova": "anskaffelsesloven",
    "anskaffingsforskrifta": "anskaffelsesforskriften",
    # Other laws commonly referenced in KOFA decisions
    "klagenemndsforskriften": "klagenemndsforskriften",
    "klagenemndforskriften": "klagenemndsforskriften",   # Common typo (missing s)
    "klagenemnsforskriften": "klagenemndsforskriften",   # Common typo (ns vs nds)
    "forsyningsforskriften": "forsyningsforskriften",
    "konsesjonskontraktforskriften": "konsesjonskontraktforskriften",
    "konkurranseloven": "konkurranseloven",
    "forvaltningsloven": "forvaltningsloven",
    "forvaltningslova": "forvaltningsloven",
    "offentleglova": "offentleglova",
    "offentlighetsloven": "offentleglova",
    "sikkerhetsloven": "sikkerhetsloven",
    "straffeloven": "straffeloven",
    "tvisteloven": "tvisteloven",
    "avtaleloven": "avtaleloven",
    # Descriptive names -> canonical
    "klagenemnd for offentlige anskaffelser": "klagenemndsforskriften",
}

# Which canonical names are "lov" vs "forskrift"
FORSKRIFT_NAMES = {
    "anskaffelsesforskriften",
    "klagenemndsforskriften",
    "forsyningsforskriften",
    "konsesjonskontraktforskriften",
}


def _classify_reference_type(canonical_name: str) -> str:
    """Determine if a canonical name is 'lov' or 'forskrift'."""
    if canonical_name in FORSKRIFT_NAMES:
        return "forskrift"
    if "forskrift" in canonical_name:
        return "forskrift"
    return "lov"


def _normalize_law_name(name: str) -> str | None:
    """Normalize a law name to its canonical form. Returns None if unknown."""
    key = name.lower().strip()
    if key in LAW_ALIASES:
        return LAW_ALIASES[key]
    # For descriptive names (from Pattern 2: "lov/forskrift om <name>"),
    # check if any alias is a substring of the descriptive name.
    # Only check multi-word aliases to avoid false positives like
    # "forskriften" matching inside "forsyningsforskriften".
    for alias, canonical in LAW_ALIASES.items():
        if " " in alias and alias in key:
            return canonical
    return None


def _normalize_section(section: str) -> str:
    """Clean up section number: remove '§' prefix, extra spaces."""
    s = section.strip()
    s = re.sub(r"^§§?\s*", "", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# =============================================================================
# Regex patterns
# =============================================================================

# Pattern 1: Named law + § section
# Matches: "anskaffelsesloven § 12", "forskriften § 20-8 (1) bokstav b"
_NAMED_LAW_RE = re.compile(
    r"([\wæøåÆØÅ-]+(?:loven|lova|forskriften|forskrifta))"  # law name
    r"\s+§§?\s*"                                              # § or §§
    r"([\d]+(?:-[\d]+)?)"                                     # section number
    r"(\s*(?:\(\d+\))?(?:\s*(?:første|andre|annet|tredje|fjerde|femte)"
    r"\s+ledd)?(?:\s*bokstav\s+[a-zæøå])?)?",                # optional subsection
    re.IGNORECASE,
)

# Pattern 2: "lov/forskrift om <name> § <section>"
_DESCRIPTIVE_LAW_RE = re.compile(
    r"(?:lov|forskrift)\s+om\s+"                              # "lov om" / "forskrift om"
    r"([\wæøåÆØÅ\s]+?)"                                      # descriptive name
    r"\s+§§?\s*"                                              # §
    r"([\d]+(?:-[\d]+)?)"                                     # section number
    r"(\s*(?:\(\d+\))?(?:\s*(?:første|andre|annet|tredje|fjerde|femte)"
    r"\s+ledd)?(?:\s*bokstav\s+[a-zæøå])?)?",                # optional subsection
    re.IGNORECASE,
)

# Pattern 3: KOFA case cross-references
# Matches: "sak 2019/491", "KOFA 2019/234", "klagenemndas sak 2020/172 avsnitt 25"
_CASE_REF_RE = re.compile(
    r"(?:klagenemndas?\s+)?(?:sak|KOFA)\s+"
    r"(\d{4}/\d+)",
    re.IGNORECASE,
)

# =============================================================================
# Extractor class
# =============================================================================


class ReferenceExtractor:
    """Extract law and case references from KOFA decision text."""

    def extract_law_references(self, text: str) -> list[LawReference]:
        """Extract all law/regulation references from text."""
        refs: list[LawReference] = []
        seen: set[tuple[str, str]] = set()  # (law_name, section) dedup

        # Pattern 1: Named law references
        for m in _NAMED_LAW_RE.finditer(text):
            raw_name = m.group(1)
            section = m.group(2)
            subsection = (m.group(3) or "").strip()
            canonical = _normalize_law_name(raw_name)
            if not canonical:
                continue
            full_section = section + (" " + subsection if subsection else "")
            key = (canonical, _normalize_section(full_section))
            if key in seen:
                continue
            seen.add(key)
            refs.append(LawReference(
                law_name=canonical,
                section=_normalize_section(full_section),
                raw_text=m.group(0).strip(),
                reference_type=_classify_reference_type(canonical),
                position=m.start(),
            ))

        # Pattern 2: Descriptive "lov/forskrift om ..." references
        for m in _DESCRIPTIVE_LAW_RE.finditer(text):
            desc_name = m.group(1).strip()
            section = m.group(2)
            subsection = (m.group(3) or "").strip()
            canonical = _normalize_law_name(desc_name)
            if not canonical:
                continue
            full_section = section + (" " + subsection if subsection else "")
            key = (canonical, _normalize_section(full_section))
            if key in seen:
                continue
            seen.add(key)
            refs.append(LawReference(
                law_name=canonical,
                section=_normalize_section(full_section),
                raw_text=m.group(0).strip(),
                reference_type=_classify_reference_type(canonical),
                position=m.start(),
            ))

        return refs

    def extract_case_references(self, text: str) -> list[CaseReference]:
        """Extract KOFA case cross-references from text."""
        refs: list[CaseReference] = []
        seen: set[str] = set()

        for m in _CASE_REF_RE.finditer(text):
            sak_nr = m.group(1)
            if sak_nr in seen:
                continue
            seen.add(sak_nr)
            refs.append(CaseReference(
                sak_nr=sak_nr,
                raw_text=m.group(0).strip(),
                position=m.start(),
            ))

        return refs

    def extract_all(
        self, text: str
    ) -> tuple[list[LawReference], list[CaseReference]]:
        """Extract all references from text."""
        return self.extract_law_references(text), self.extract_case_references(text)
