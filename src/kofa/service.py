"""
KOFA service layer.

Business logic and response formatting for KOFA MCP tools.
"""

from __future__ import annotations

import logging

from kofa.supabase_backend import KofaSupabaseBackend

logger = logging.getLogger(__name__)


class KofaService:
    """Service layer wrapping backend with formatted responses."""

    def __init__(self, backend: KofaSupabaseBackend | None = None):
        self.backend = backend or KofaSupabaseBackend()

    def search(self, query: str, limit: int = 20) -> str:
        """Full-text search across KOFA cases."""
        results = self.backend.search(query, limit)

        if not results:
            return f"Ingen treff for: {query}"

        lines = [f"## Søk: {query}\n"]
        lines.append(f"Fant {len(results)} saker:\n")

        for r in results:
            lines.append(self._format_case_summary(r))

        return "\n".join(lines)

    def get_case(self, sak_nr: str) -> str:
        """Get a specific case by case number."""
        case = self.backend.get_case(sak_nr)

        if not case:
            return f"Fant ikke sak: {sak_nr}"

        return self._format_case_detail(case)

    def get_decision_text(self, sak_nr: str, section: str | None = None) -> str:
        """Get decision text for a case, optionally filtered by section."""
        case = self.backend.get_case(sak_nr)
        if not case:
            return f"Fant ikke sak: {sak_nr}"

        paragraphs = self.backend.get_decision_text(sak_nr, section)
        if not paragraphs:
            if section:
                return f"Ingen avgjørelsestekst i seksjon '{section}' for sak {sak_nr}."
            return (
                f"Ingen avgjørelsestekst tilgjengelig for sak {sak_nr}. "
                f"Bruk PDF-lenken fra hent_sak() for å lese avgjørelsen."
            )

        if section:
            return self._format_decision_section(sak_nr, section, paragraphs)
        else:
            return self._format_decision_toc(sak_nr, paragraphs)

    def search_decision_text(
        self,
        query: str,
        section: str | None = None,
        limit: int = 20,
    ) -> str:
        """Full-text search in decision text paragraphs."""
        results = self.backend.search_decision_text(query, section, limit)

        if not results:
            section_label = f" (seksjon: {section})" if section else ""
            return f"Ingen treff i avgjørelsestekst for: {query}{section_label}"

        lines = [f"## Søk i avgjørelsestekst: {query}\n"]
        if section:
            lines.append(f"*Filtrert på seksjon: {section}*\n")
        lines.append(f"Fant {len(results)} treff:\n")

        for r in results:
            sak_nr = r.get("sak_nr", "?")
            sec = r.get("section", "")
            para_nr = r.get("paragraph_number", "?")
            text = r.get("text", "")
            rank = r.get("rank", 0)
            innklaget = r.get("innklaget", "")
            avgjoerelse = r.get("avgjoerelse", "")

            snippet = text[:300] + "..." if len(text) > 300 else text
            parts = [f"### {sak_nr} — {sec} ({para_nr})"]
            if innklaget:
                parts.append(f"**Innklaget:** {innklaget}")
            if avgjoerelse:
                parts.append(f"**Avgjoerelse:** {avgjoerelse}")
            parts.append(f"*Rank: {rank:.3f}*")
            parts.append(f"\n{snippet}\n")
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def semantic_search(
        self,
        query: str,
        section: str | None = None,
        limit: int = 10,
    ) -> str:
        """Semantic (hybrid vector + FTS) search in decision text."""
        try:
            from kofa.vector_search import KofaVectorSearch

            vs = KofaVectorSearch()
            results = vs.search(query, limit=limit, section=section)
        except Exception as e:
            logger.warning(f"Semantic search failed, falling back to FTS: {e}")
            return self.search_decision_text(query, section, limit)

        if not results:
            section_label = f" (seksjon: {section})" if section else ""
            return f"Ingen treff for semantisk søk: {query}{section_label}"

        lines = [f"## Semantisk søk: {query}\n"]
        if section:
            lines.append(f"*Filtrert på seksjon: {section}*\n")
        lines.append(f"Fant {len(results)} treff:\n")

        for r in results:
            snippet = r.text[:300] + "..." if len(r.text) > 300 else r.text
            parts = [f"### {r.sak_nr} — {r.section} ({r.paragraph_number})"]
            if r.innklaget:
                parts.append(f"**Innklaget:** {r.innklaget}")
            if r.avgjoerelse:
                parts.append(f"**Avgjoerelse:** {r.avgjoerelse}")
            parts.append(
                f"*Score: {r.combined_score:.3f} "
                f"(vektor: {r.similarity:.3f}, FTS: {r.fts_rank:.3f})*"
            )
            parts.append(f"\n{snippet}\n")
            parts.append(f'-> `hent_avgjoerelse("{r.sak_nr}", "{r.section}")`\n')
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def recent_cases(
        self,
        limit: int = 20,
        sakstype: str | None = None,
        avgjoerelse: str | None = None,
        innklaget: str | None = None,
    ) -> str:
        """Get recent cases with optional filters."""
        cases = self.backend.recent_cases(limit, sakstype, avgjoerelse, innklaget)

        if not cases:
            return "Ingen saker funnet med valgte filtre."

        lines = ["## Siste KOFA-saker\n"]

        filters = []
        if sakstype:
            filters.append(f"sakstype={sakstype}")
        if avgjoerelse:
            filters.append(f"avgjørelse={avgjoerelse}")
        if innklaget:
            filters.append(f"innklaget={innklaget}")
        if filters:
            lines.append(f"*Filter: {', '.join(filters)}*\n")

        lines.append(f"Viser {len(cases)} saker:\n")

        for c in cases:
            lines.append(self._format_case_summary(c))

        return "\n".join(lines)

    def statistics(self, aar: int | None = None, gruppering: str = "avgjoerelse") -> str:
        """Get aggregate statistics."""
        stats = self.backend.statistics(aar, gruppering)

        if not stats:
            return "Ingen statistikk tilgjengelig."

        year_label = f" ({aar})" if aar else " (alle år)"
        lines = [f"## KOFA-statistikk{year_label}\n"]
        lines.append(f"Gruppert etter: **{gruppering}**\n")

        for row in stats:
            label = row.get("label", "Ukjent")
            count = row.get("count", 0)
            lines.append(f"- **{label}**: {count} saker")

        total = sum(r.get("count", 0) for r in stats)
        lines.append(f"\n**Totalt:** {total} saker")

        return "\n".join(lines)

    def finn_praksis(
        self,
        lov: str,
        paragraf: str | None = None,
        paragrafer: list[str] | None = None,
        limit: int = 20,
    ) -> str:
        """Find KOFA cases citing specific law sections."""
        from kofa.reference_extractor import LAW_ALIASES, _normalize_section

        # Validate law name
        lov = lov.strip()
        if not lov:
            return "Feil: 'lov' er påkrevd. Bruk f.eks. 'anskaffelsesforskriften' eller 'foa'."

        # Normalize law name
        canonical = LAW_ALIASES.get(lov.lower())
        if not canonical:
            canonical = lov.lower()

        # Normalize and clean section input — filter empty strings, deduplicate
        if paragrafer:
            paragrafer = list(dict.fromkeys(_normalize_section(p) for p in paragrafer if p.strip()))
            if len(paragrafer) == 1:
                paragraf = paragrafer[0]
                paragrafer = None
            elif not paragrafer:
                paragrafer = None
        if paragraf:
            paragraf = _normalize_section(paragraf)
            if not paragraf:
                paragraf = None

        # Multi-section AND search
        if paragrafer:
            return self._finn_praksis_multi(canonical, lov, paragrafer, limit)

        # Single-section or all-sections search (existing behavior)
        results = self.backend.find_by_law_reference(canonical, paragraf, limit)

        if not results:
            section_label = f" § {paragraf}" if paragraf else ""
            return f"Ingen KOFA-saker funnet som refererer til {lov}{section_label}"

        section_label = f" § {paragraf}" if paragraf else ""
        lines = [f"## KOFA-praksis: {lov}{section_label}\n"]
        lines.append(f"Fant {len(results)} saker:\n")

        for r in results:
            lines.append(self._format_law_ref_result(r))

        return "\n".join(lines)

    def _finn_praksis_multi(
        self,
        canonical: str,
        lov: str,
        paragrafer: list[str],
        limit: int,
    ) -> str:
        """AND search: find cases citing ALL specified sections."""
        results = self.backend.find_cases_by_sections(canonical, paragrafer, limit)

        if not results:
            return self._no_results_multi(canonical, lov, paragrafer)

        # Group by sak_nr
        by_case: dict[str, list[dict]] = {}
        for r in results:
            by_case.setdefault(r["sak_nr"], []).append(r)

        section_label = " + ".join(f"§ {p}" for p in paragrafer)
        lines = [f"## KOFA-praksis: {lov} {section_label}\n"]
        lines.append(f"Fant {len(by_case)} saker som refererer alle bestemmelsene:\n")

        for sak_nr, refs in by_case.items():
            case_info = refs[0].get("kofa_cases", {}) or {}
            sections_found = sorted({r["law_section"] for r in refs})
            reg_version = refs[0].get("regulation_version", "")
            version_label = " (gammel forskrift)" if reg_version == "old" else ""

            parts = [f"### {sak_nr}{version_label}"]
            parts.append(f"**Refererte paragrafer:** {', '.join(sections_found)}")

            innklaget = case_info.get("innklaget", "")
            if innklaget:
                parts.append(f"**Innklaget:** {innklaget}")
            avgjoerelse = case_info.get("avgjoerelse", "")
            if avgjoerelse:
                parts.append(f"**Avgjoerelse:** {avgjoerelse}")
            saken_gjelder = case_info.get("saken_gjelder", "")
            if saken_gjelder:
                parts.append(f"*{saken_gjelder}*")
            avsluttet = case_info.get("avsluttet", "")
            if avsluttet:
                parts.append(f"Avsluttet: {avsluttet}")

            for ref in refs:
                context = ref.get("context", "")
                if context:
                    snippet = context[:200] + "..." if len(context) > 200 else context
                    parts.append(f"> **§ {ref['law_section']}:** {snippet}")

            parts.append("")
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def _no_results_multi(self, canonical: str, lov: str, paragrafer: list[str]) -> str:
        """Enriched no-results response for multi-section AND search."""
        section_label = " + ".join(f"§ {p}" for p in paragrafer)
        lines = [
            f"Ingen KOFA-saker funnet som refererer alle: {lov} {section_label}\n",
            "**Antall saker per bestemmelse separat:**\n",
        ]
        for p in paragrafer:
            count = self.backend.count_cases_by_section(canonical, p)
            lines.append(f"- {lov} § {p}: {count} saker")

        lines.append("\nBruk `finn_praksis` med enkelt paragraf for å se sakene separat.")
        return "\n".join(lines)

    @staticmethod
    def _format_law_ref_result(r: dict) -> str:
        """Format a single law reference result as markdown."""
        sak_nr = r.get("sak_nr", "?")
        law_section = r.get("law_section", "")
        case_info = r.get("kofa_cases", {}) or {}
        reg_version = r.get("regulation_version", "")
        version_label = " (gammel forskrift)" if reg_version == "old" else ""

        parts = [f"### {sak_nr}{version_label}"]
        if law_section:
            parts.append(f"**Referert paragraf:** {law_section}")
        innklaget = case_info.get("innklaget", "")
        if innklaget:
            parts.append(f"**Innklaget:** {innklaget}")
        avgjoerelse = case_info.get("avgjoerelse", "")
        if avgjoerelse:
            parts.append(f"**Avgjoerelse:** {avgjoerelse}")
        saken_gjelder = case_info.get("saken_gjelder", "")
        if saken_gjelder:
            parts.append(f"*{saken_gjelder}*")
        avsluttet = case_info.get("avsluttet", "")
        if avsluttet:
            parts.append(f"Avsluttet: {avsluttet}")

        context = r.get("context", "")
        if context:
            snippet = context[:200] + "..." if len(context) > 200 else context
            parts.append(f"> {snippet}")

        parts.append("")
        return "\n".join(parts)

    def related_cases(self, sak_nr: str) -> str:
        """Find cases related to a given case via cross-references."""
        data = self.backend.find_related_cases(sak_nr)

        cites = data.get("cites", [])
        cited_by = data.get("cited_by", [])

        if not cites and not cited_by:
            return f"Ingen kryssreferanser funnet for sak {sak_nr}."

        lines = [f"## Relaterte saker: {sak_nr}\n"]

        if cites:
            lines.append(f"### Saken refererer til ({len(cites)} saker)\n")
            for c in cites:
                lines.append(self._format_ref_line(c))
            lines.append("")

        if cited_by:
            lines.append(f"### Sitert av ({len(cited_by)} saker)\n")
            for c in cited_by:
                lines.append(self._format_ref_line(c))
            lines.append("")

        return "\n".join(lines)

    def most_cited(self, limit: int = 20) -> str:
        """Find the most frequently cited KOFA cases."""
        results = self.backend.most_cited_cases(limit)

        if not results:
            return "Ingen siteringsdata tilgjengelig."

        lines = ["## Mest siterte KOFA-saker\n"]
        lines.append("Basert på kryssreferanser i avgjørelsestekst.\n")

        for r in results:
            sak_nr = r.get("sak_nr", "?")
            count = r.get("cited_count", 0)
            innklaget = r.get("innklaget", "")
            avgjoerelse = r.get("avgjoerelse", "")
            saken_gjelder = r.get("saken_gjelder", "")

            parts = [f"- **{sak_nr}** — sitert {count} ganger"]
            details = []
            if innklaget:
                details.append(innklaget)
            if avgjoerelse:
                details.append(avgjoerelse)
            if details:
                parts[0] += f" ({', '.join(details)})"
            if saken_gjelder:
                parts.append(f"  *{saken_gjelder}*")

            lines.append("\n".join(parts))

        return "\n".join(lines)

    def eu_praksis(self, eu_case_id: str, limit: int = 20) -> str:
        """Find KOFA cases citing a specific EU Court case."""
        results = self.backend.find_by_eu_case(eu_case_id, limit)

        if not results:
            return f"Ingen KOFA-saker funnet som refererer til EU-sak {eu_case_id}."

        # Get case name from first result that has one
        eu_name = ""
        for r in results:
            if r.get("eu_case_name"):
                eu_name = f" {r['eu_case_name']}"
                break

        lines = [f"## EU-domstolspraksis i KOFA: {eu_case_id}{eu_name}\n"]
        lines.append(f"Fant {len(results)} KOFA-saker som refererer til denne EU-dommen:\n")

        for r in results:
            sak_nr = r.get("sak_nr", "?")
            case_info = r.get("kofa_cases", {}) or {}
            innklaget = case_info.get("innklaget", "")
            avgjoerelse = case_info.get("avgjoerelse", "")
            saken_gjelder = case_info.get("saken_gjelder", "")

            parts = [f"### {sak_nr}"]
            if innklaget:
                parts.append(f"**Innklaget:** {innklaget}")
            if avgjoerelse:
                parts.append(f"**Avgjoerelse:** {avgjoerelse}")
            if saken_gjelder:
                parts.append(f"*{saken_gjelder}*")

            context = r.get("context", "")
            if context:
                snippet = context[:200] + "..." if len(context) > 200 else context
                parts.append(f"> {snippet}")

            parts.append("")
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def hent_eu_dom(self, eu_case_id: str, seksjon: str | None = None) -> str:
        """
        Get EU Court judgment text, with optional section filtering.

        Without seksjon: returns metadata + table of contents with char counts.
        With seksjon: returns the requested section text.

        Sections are split on-the-fly using text markers:
        - sammendrag: text before "JUDGMENT OF THE COURT"
        - begrunnelse: text between "JUDGMENT OF THE COURT" and "On those grounds"
        - domsslutning: text from "On those grounds" to end
        """
        case_law = self.backend.get_eu_case_law(eu_case_id)

        if not case_law:
            return (
                f"Ingen EU-dom funnet for {eu_case_id}. "
                f"Sjekk at saksnummeret er korrekt (f.eks. 'C-19/00'). "
                f"Bruk `mest_siterte_eu()` for å se tilgjengelige EU-dommer."
            )

        full_text = case_law.get("full_text", "")
        sections = self._split_eu_judgment_sections(full_text)

        if seksjon:
            seksjon = seksjon.lower().strip()
            if seksjon not in sections:
                available = ", ".join(f"'{s}'" for s in sections if s != "full")
                return f"Ukjent seksjon: '{seksjon}'. Tilgjengelige seksjoner: {available}"
            section_text = sections[seksjon]
            if not section_text:
                return f"Seksjonen '{seksjon}' er tom for {eu_case_id}."

            section_labels = {
                "sammendrag": "Sammendrag (Summary)",
                "begrunnelse": "Begrunnelse (Grounds)",
                "domsslutning": "Domsslutning (Operative part)",
            }
            label = section_labels.get(seksjon, seksjon)
            lines = [f"## {eu_case_id} — {label}\n"]
            lines.append(f"*{len(section_text):,} tegn*\n")
            lines.append(section_text)
            return "\n".join(lines)

        # No section specified — return metadata + TOC
        lines = [f"## EU-dom: {eu_case_id}\n"]

        case_name = case_law.get("case_name", "")
        if case_name:
            lines.append(f"**Navn:** {case_name}")
        judgment_date = case_law.get("judgment_date", "")
        if judgment_date:
            lines.append(f"**Dato:** {judgment_date}")
        subject = case_law.get("subject", "")
        if subject:
            lines.append(f"**Emne:** {subject}")
        language = case_law.get("language", "EN")
        lines.append(f"**Språk:** {language}")
        source_url = case_law.get("source_url", "")
        if source_url:
            lines.append(f"**Kilde:** {source_url}")

        # TOC with char counts
        lines.append("\n### Innholdsfortegnelse\n")
        section_labels = {
            "sammendrag": "Sammendrag (Summary)",
            "begrunnelse": "Begrunnelse (Grounds)",
            "domsslutning": "Domsslutning (Operative part)",
        }
        for sec_key, sec_label in section_labels.items():
            text = sections.get(sec_key, "")
            chars = len(text)
            tokens = chars // 4
            lines.append(f"- **{sec_label}:** {chars:,} tegn (~{tokens:,} tokens)")

        total = len(full_text)
        lines.append(f"\n**Totalt:** {total:,} tegn (~{total // 4:,} tokens)")

        lines.append(
            "\nBruk `hent_eu_dom(eu_case_id, seksjon='begrunnelse')` for å lese en bestemt seksjon."
        )

        return "\n".join(lines)

    @staticmethod
    def _split_eu_judgment_sections(full_text: str) -> dict[str, str]:
        """
        Split EU judgment text into sections on-the-fly.

        Uses text markers (in priority order):
        - "JUDGMENT OF THE COURT" splits summary from grounds
        - "Grounds" (old format TOC heading) as fallback for grounds start
        - "On those grounds" splits grounds from operative part
        - "Operative part" (old format TOC heading) as fallback

        Returns dict with keys: sammendrag, begrunnelse, domsslutning
        """
        import re

        # Find grounds start: "JUDGMENT OF THE COURT" or fallback to "Grounds" heading
        judgment_marker = re.search(
            r"JUDGMENT OF THE (?:COURT|GENERAL COURT)",
            full_text,
        )
        if not judgment_marker:
            judgment_marker = re.search(r"\nGrounds\n", full_text)

        # Find operative part: "On those grounds" or fallback to "Operative part" heading
        operative_marker = re.search(
            r"On those grounds.*?(?:hereby|:)\s*",
            full_text,
            re.DOTALL,
        )
        if not operative_marker:
            operative_marker = re.search(r"\nOperative part\n", full_text)

        if judgment_marker and operative_marker:
            sammendrag = full_text[: judgment_marker.start()].strip()
            begrunnelse = full_text[judgment_marker.start() : operative_marker.start()].strip()
            domsslutning = full_text[operative_marker.start() :].strip()
        elif judgment_marker:
            sammendrag = full_text[: judgment_marker.start()].strip()
            begrunnelse = full_text[judgment_marker.start() :].strip()
            domsslutning = ""
        else:
            # No markers found — return full text as begrunnelse
            sammendrag = ""
            begrunnelse = full_text.strip()
            domsslutning = ""

        return {
            "sammendrag": sammendrag,
            "begrunnelse": begrunnelse,
            "domsslutning": domsslutning,
        }

    def mest_siterte_eu(self, limit: int = 20) -> str:
        """Find the most frequently cited EU Court cases in KOFA decisions."""
        results = self.backend.most_cited_eu_cases(limit)

        if not results:
            return "Ingen EU-siteringsdata tilgjengelig."

        lines = ["## Mest siterte EU-dommer i KOFA\n"]
        lines.append("Basert på referanser i avgjørelsestekst.\n")

        for r in results:
            case_id = r.get("eu_case_id", "?")
            name = r.get("eu_case_name", "")
            count = r.get("cited_count", 0)

            name_str = f" {name}" if name else ""
            lines.append(f"- **{case_id}{name_str}** — sitert i {count} KOFA-saker")

        return "\n".join(lines)

    # =========================================================================
    # Forarbeider (legislative preparatory works)
    # =========================================================================

    def hent_forarbeide(self, doc_id: str | None = None, seksjon: str | None = None) -> str:
        """
        Browse forarbeider (propositions and NOU reports).

        Three modes:
        1. No args → list all documents
        2. doc_id only → show table of contents with token estimates
        3. doc_id + seksjon → show section text (prefix match)
        """
        # Mode 1: List all documents
        if not doc_id:
            docs = self.backend.list_forarbeider()
            if not docs:
                return "Ingen forarbeider tilgjengelig."

            lines = ["## Forarbeider\n"]
            lines.append(f"{len(docs)} dokumenter tilgjengelig:\n")

            for doc in docs:
                title = doc.get("title", doc.get("doc_id", "?"))
                did = doc.get("doc_id", "?")
                doc_type = doc.get("doc_type", "")
                session = doc.get("session", "")
                section_count = doc.get("section_count", 0)
                char_count = doc.get("char_count", 0)
                tokens = char_count // 4

                lines.append(f"### {title}")
                lines.append(f"**ID:** `{did}`")
                meta_parts = []
                if doc_type:
                    meta_parts.append(f"**Type:** {doc_type}")
                if session:
                    meta_parts.append(f"**Sesjon:** {session}")
                if meta_parts:
                    lines.append(" | ".join(meta_parts))
                lines.append(
                    f"**Omfang:** {section_count} seksjoner, "
                    f"{char_count:,} tegn (~{tokens:,} tokens)"
                )
                lines.append("")

            lines.append("Bruk `hent_forarbeide(doc_id='...')` for innholdsfortegnelse.")
            return "\n".join(lines)

        # Mode 2 & 3: Need document metadata
        doc = self.backend.get_forarbeide(doc_id)
        if not doc:
            return (
                f"Fant ikke forarbeide: {doc_id}. "
                f"Bruk `hent_forarbeide()` for å se tilgjengelige "
                f"dokumenter."
            )

        title = doc.get("title", doc_id)

        # Mode 3: Show section text
        if seksjon:
            sections = self.backend.get_forarbeider_sections(doc_id, seksjon)
            if not sections:
                return (
                    f"Fant ingen seksjoner som matcher '{seksjon}' i "
                    f"{title}. Bruk "
                    f"`hent_forarbeide(doc_id='{doc_id}')` for "
                    f"innholdsfortegnelse."
                )

            first = sections[0]
            header_sec = first.get("section_number", seksjon)
            header_title = first.get("title", "")
            header = f"## {title} — {header_sec}"
            if header_title:
                header += f" {header_title}"
            lines = [header, ""]

            for s in sections:
                sec_num = s.get("section_number", "")
                sec_title = s.get("title", "")
                level = s.get("level", 2)
                text = s.get("text", "")

                # Heading level: level 1 → ##, 2 → ###, etc.
                hashes = "#" * min(level + 1, 6)
                heading = f"{hashes} {sec_num}"
                if sec_title:
                    heading += f" {sec_title}"
                lines.append(heading)
                lines.append("")
                if text.strip():
                    lines.append(text)
                    lines.append("")

            return "\n".join(lines)

        # Mode 2: Show TOC
        all_sections = self.backend.get_forarbeider_sections(doc_id)
        total_chars = doc.get("char_count", 0)
        total_tokens = total_chars // 4
        section_count = doc.get("section_count", 0)

        lines = [f"## {title} — Innholdsfortegnelse\n"]
        lines.append(
            f"{section_count} seksjoner, {total_chars:,} tegn (~{total_tokens:,} tokens)\n"
        )

        # Group by top-level section (level 1)
        lines.append("| # | Seksjon | Tegn | ~Tokens |")
        lines.append("|---|---------|-----:|--------:|")

        # Build TOC: for each level-1 section, sum chars of it
        # and its subsections
        current_l1: dict | None = None
        l1_chars = 0

        for s in all_sections:
            level = s.get("level", 1)
            if level == 1:
                # Flush previous level-1 section
                if current_l1 is not None:
                    sec_num = current_l1.get("section_number", "?")
                    sec_title = current_l1.get("title", "")
                    tokens = l1_chars // 4
                    lines.append(f"| {sec_num} | {sec_title} | {l1_chars:,} | {tokens:,} |")
                current_l1 = s
                l1_chars = s.get("char_count", 0) or 0
            else:
                l1_chars += s.get("char_count", 0) or 0

        # Flush last level-1 section
        if current_l1 is not None:
            sec_num = current_l1.get("section_number", "?")
            sec_title = current_l1.get("title", "")
            tokens = l1_chars // 4
            lines.append(f"| {sec_num} | {sec_title} | {l1_chars:,} | {tokens:,} |")

        lines.append(
            f"\nBruk `hent_forarbeide(doc_id='{doc_id}', seksjon='...')` for å lese en seksjon."
        )
        return "\n".join(lines)

    def sok_forarbeider(self, query: str, doc_id: str | None = None, limit: int = 20) -> str:
        """Full-text search in forarbeider sections."""
        results = self.backend.search_forarbeider(query, doc_id, limit)

        if not results:
            doc_label = f" (dokument: {doc_id})" if doc_id else ""
            return f"Ingen treff i forarbeider for: {query}{doc_label}"

        lines = [f"## Søk i forarbeider: {query}\n"]
        if doc_id:
            lines.append(f"*Filtrert på dokument: {doc_id}*\n")
        lines.append(f"Fant {len(results)} treff:\n")

        for r in results:
            doc_title = r.get("doc_title", r.get("doc_id", "?"))
            sec_num = r.get("section_number", "?")
            sec_title = r.get("title", "")
            rank = r.get("rank", 0)
            text = r.get("text", "")
            char_count = r.get("char_count", 0)
            r_doc_id = r.get("doc_id", "?")

            heading = f"### {doc_title} — {sec_num}"
            if sec_title:
                heading += f" {sec_title}"
            snippet = text[:300] + "..." if len(text) > 300 else text

            parts = [heading]
            parts.append(f"*Rank: {rank:.3f} | {char_count} tegn*")
            parts.append(f"\n{snippet}\n")
            parts.append(f'-> `hent_forarbeide("{r_doc_id}", "{sec_num}")`')
            parts.append("")
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def semantisk_sok_forarbeider(
        self,
        query: str,
        doc_id: str | None = None,
        limit: int = 10,
    ) -> str:
        """Semantic (hybrid vector + FTS) search in forarbeider."""
        try:
            from kofa.vector_search import ForarbeiderVectorSearch

            vs = ForarbeiderVectorSearch()
            results = vs.search(query, limit=limit, doc_id=doc_id)
        except Exception as e:
            logger.warning(f"Forarbeider semantic search failed, falling back to FTS: {e}")
            return self.sok_forarbeider(query, doc_id, limit)

        if not results:
            doc_label = f" (dokument: {doc_id})" if doc_id else ""
            return f"Ingen treff for semantisk søk i forarbeider: {query}{doc_label}"

        lines = [f"## Semantisk søk i forarbeider: {query}\n"]
        if doc_id:
            lines.append(f"*Filtrert på dokument: {doc_id}*\n")
        lines.append(f"Fant {len(results)} treff:\n")

        for r in results:
            doc_title = getattr(r, "doc_title", "?")
            sec_num = getattr(r, "section_number", "?")
            sec_title = getattr(r, "title", "")
            text = getattr(r, "text", "")
            r_doc_id = getattr(r, "doc_id", "?")

            heading = f"### {doc_title} — {sec_num}"
            if sec_title:
                heading += f" {sec_title}"
            snippet = text[:300] + "..." if len(text) > 300 else text

            combined = getattr(r, "combined_score", 0)
            sim = getattr(r, "similarity", 0)
            fts = getattr(r, "fts_rank", 0)

            parts = [heading]
            parts.append(f"*Score: {combined:.3f} (vektor: {sim:.3f}, FTS: {fts:.3f})*")
            parts.append(f"\n{snippet}\n")
            parts.append(f'-> `hent_forarbeide("{r_doc_id}", "{sec_num}")`')
            parts.append("")
            lines.append("\n".join(parts))

        return "\n".join(lines)

    def finn_forarbeider(
        self,
        lov: str,
        paragraf: str | None = None,
        limit: int = 20,
    ) -> str:
        """Find forarbeider sections citing a specific law provision."""
        from kofa.reference_extractor import LAW_ALIASES, _normalize_section

        lov = lov.strip()
        if not lov:
            return "Feil: 'lov' er påkrevd. Bruk f.eks. 'anskaffelsesforskriften' eller 'foa'."

        canonical = LAW_ALIASES.get(lov.lower())
        if not canonical:
            canonical = lov.lower()

        if paragraf:
            paragraf = _normalize_section(paragraf)
            if not paragraf:
                paragraf = None

        results = self.backend.find_forarbeider_by_law_reference(canonical, paragraf, limit)

        if not results:
            section_label = f" § {paragraf}" if paragraf else ""
            return f"Ingen forarbeider-seksjoner funnet som refererer til {lov}{section_label}"

        section_label = f" § {paragraf}" if paragraf else ""
        lines = [f"## Forarbeider: {lov}{section_label}\n"]
        lines.append(f"Fant {len(results)} seksjoner:\n")

        for r in results:
            doc_title = ""
            fa_meta = r.get("kofa_forarbeider")
            if fa_meta:
                doc_title = fa_meta.get("title", "")
            section_nr = r.get("section_number", "")
            doc_id = r.get("doc_id", "")
            law_section = r.get("law_section", "")
            context = r.get("context", "")
            snippet = context[:200] + "..." if len(context) > 200 else context

            parts = [f"### {doc_title} — {section_nr}"]
            if law_section:
                parts.append(f"**Referert paragraf:** § {law_section}")
            if snippet:
                parts.append(f"> {snippet}")
            parts.append(f'-> `hent_forarbeide("{doc_id}", "{section_nr}")`\n')
            lines.append("\n".join(parts))

        return "\n".join(lines)

    @staticmethod
    def _format_ref_line(case: dict) -> str:
        """Format a cross-referenced case as a compact line."""
        sak_nr = case.get("sak_nr", "?")
        innklaget = case.get("innklaget", "")
        avgjoerelse = case.get("avgjoerelse", "")
        saken_gjelder = case.get("saken_gjelder", "")

        parts = [f"- **{sak_nr}**"]
        details = []
        if innklaget:
            details.append(innklaget)
        if avgjoerelse:
            details.append(avgjoerelse)
        if details:
            parts[0] += f" — {', '.join(details)}"
        if saken_gjelder:
            parts.append(f"  *{saken_gjelder}*")

        return "\n".join(parts)

    def sync(
        self,
        scrape: bool = False,
        pdf: bool = False,
        references: bool = False,
        eu_cases: bool = False,
        forarbeider: bool = False,
        force: bool = False,
        limit: int | None = None,
        max_time: int = 0,
        delay: float = 1.0,
        max_errors: int = 20,
        verbose: bool = False,
        refresh_pending: bool = False,
    ) -> str:
        """Run sync operation."""
        lines = ["## Synkronisering\n"]

        # WP API sync (skip if only doing PDF, reference, EU, or forarbeider)
        if not pdf and not references and not eu_cases and not forarbeider:
            wp_stats = self.backend.sync_from_wp_api(force=force, verbose=verbose)
            lines.append("### WordPress API")
            lines.append(f"- Hentet **{wp_stats['upserted']}** saker fra {wp_stats['pages']} sider")
            if wp_stats["errors"]:
                lines.append(f"- {wp_stats['errors']} feil")

        # HTML scraping (optional)
        if scrape:
            html_stats = self.backend.sync_html_metadata(
                limit=limit,
                max_time=max_time,
                delay=delay,
                max_errors=max_errors,
                verbose=verbose,
                force=force,
                refresh_pending=refresh_pending,
            )
            lines.append("\n### HTML-skraping")
            lines.append(f"- Beriket **{html_stats['scraped']}** saker med metadata")
            if html_stats["errors"]:
                lines.append(f"- {html_stats['errors']} feil")
            if html_stats["skipped"]:
                lines.append(f"- {html_stats['skipped']} hoppet over")
            if html_stats.get("stopped_reason"):
                lines.append(f"- Stoppet: {html_stats['stopped_reason']}")

        # PDF text extraction (optional)
        if pdf:
            pdf_stats = self.backend.sync_pdf_text(
                limit=limit,
                max_time=max_time,
                delay=delay,
                max_errors=max_errors,
                verbose=verbose,
                force=force,
            )
            lines.append("\n### PDF-ekstraksjon")
            lines.append(
                f"- Ekstrahert **{pdf_stats['extracted']}** avgjørelser ({pdf_stats['total_paragraphs']} avsnitt)"
            )
            if pdf_stats["errors"]:
                lines.append(f"- {pdf_stats['errors']} feil")
            if pdf_stats["skipped"]:
                lines.append(f"- {pdf_stats['skipped']} hoppet over")
            if pdf_stats.get("stopped_reason"):
                lines.append(f"- Stoppet: {pdf_stats['stopped_reason']}")

        # Reference extraction (optional)
        if references:
            ref_stats = self.backend.sync_references(
                limit=limit,
                verbose=verbose,
                force=force,
            )
            lines.append("\n### Referanse-ekstraksjon")
            lines.append(
                f"- Prosessert **{ref_stats['cases_processed']}** saker "
                f"({ref_stats['law_refs']} lovhenvisninger, {ref_stats['case_refs']} sakskryssreferanser, "
                f"{ref_stats.get('eu_refs', 0)} EU-referanser, "
                f"{ref_stats.get('court_refs', 0)} rettsavgjørelser)"
            )
            if ref_stats["errors"]:
                lines.append(f"- {ref_stats['errors']} feil")
            if ref_stats.get("stopped_reason"):
                lines.append(f"- Stoppet: {ref_stats['stopped_reason']}")

        # EU case law fetching (optional)
        if eu_cases:
            eu_stats = self.backend.sync_eu_case_law(
                limit=limit,
                delay=delay,
                max_errors=max_errors,
                verbose=verbose,
                force=force,
            )
            lines.append("\n### EU-domstolspraksis (EUR-Lex)")
            lines.append(f"- Hentet **{eu_stats['fetched']}** EU-dommer fra EUR-Lex")
            if eu_stats["errors"]:
                lines.append(f"- {eu_stats['errors']} feil")
            if eu_stats["skipped"]:
                lines.append(f"- {eu_stats['skipped']} hoppet over (404)")
            if eu_stats.get("stopped_reason"):
                lines.append(f"- Stoppet: {eu_stats['stopped_reason']}")

        # Forarbeider import (optional)
        if forarbeider:
            import os

            pdf_dir = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "forarbeider")
            pdf_dir = os.path.normpath(pdf_dir)
            fa_stats = self.backend.sync_forarbeider(
                pdf_dir=pdf_dir,
                force=force,
                verbose=verbose,
            )
            lines.append("\n### Forarbeider (PDF-import)")
            lines.append(
                f"- Importert **{fa_stats['documents']}** dokumenter "
                f"({fa_stats['sections']} seksjoner)"
            )
            if fa_stats["errors"]:
                lines.append(f"- {fa_stats['errors']} feil")

            # Extract references from imported text
            ref_stats = self.backend.sync_forarbeider_references(
                force=force,
                verbose=verbose,
            )
            if ref_stats["documents"] > 0:
                lines.append(
                    f"- Referanser: **{ref_stats['law_refs']}** lovhenvisninger, "
                    f"**{ref_stats['eu_refs']}** EU-referanser "
                    f"(fra {ref_stats['documents']} dokumenter)"
                )
            if ref_stats["errors"]:
                lines.append(f"- {ref_stats['errors']} referansefeil")

        return "\n".join(lines)

    def get_status(self) -> str:
        """Get sync status with pipeline coverage."""
        status = self.backend.get_sync_status()

        if not status or status.get("cases", 0) == 0:
            return """## KOFA Status

**Status:** Ikke synkronisert

Kjør `sync()` for å laste ned saker fra KOFA."""

        total = status.get("cases", 0)
        lines = ["## KOFA Status\n"]
        lines.append(f"- **Totalt saker:** {total}")
        lines.append(f"- **Beriket (med metadata):** {status.get('enriched', 0)}")

        # Pipeline coverage
        pipeline = status.get("pipeline")
        if pipeline:
            lines.append("\n### Pipeline-dekning\n")
            lines.append("| Steg | Saker | Av total | % |")
            lines.append("|------|------:|--------:|---:|")

            steps = [
                ("PDF-URL", pipeline.get("have_pdf_url", 0)),
                ("PDF-tekst ekstrahert", pipeline.get("have_text", 0)),
                ("Seksjonsinndelt", pipeline.get("sectioned", 0)),
                ("Lovhenvisninger", pipeline.get("law_ref_cases", 0)),
                ("Sakskryssreferanser", pipeline.get("case_ref_cases", 0)),
                ("EU-referanser", pipeline.get("eu_ref_cases", 0)),
                ("Rettsavgjørelser", pipeline.get("court_ref_cases", 0)),
            ]
            eu_case_law = pipeline.get("eu_case_law_count", 0)
            for label, count in steps:
                pct = round(100 * count / total) if total > 0 else 0
                lines.append(f"| {label} | {count:,} | {total:,} | {pct}% |")

            raw_only = pipeline.get("raw_only", 0)
            if raw_only > 0:
                lines.append(f"\n- **Raw-only (uten seksjonering):** {raw_only}")

            paragraphs = pipeline.get("total_paragraphs", 0)
            embeddings = pipeline.get("embeddings", 0)
            if paragraphs > 0:
                emb_pct = round(100 * embeddings / paragraphs) if paragraphs > 0 else 0
                lines.append(f"- **Avsnitt (non-raw):** {paragraphs:,}")
                lines.append(f"- **Embeddings:** {embeddings:,} ({emb_pct}%)")

            if eu_case_law > 0:
                eu_ref_unique = pipeline.get("eu_ref_cases", 0)
                lines.append(
                    f"- **EU-dommer (fulltekst):** {eu_case_law}"
                    + (f" av ~{eu_ref_unique} refererte" if eu_ref_unique else "")
                )

        # Sync cursors
        for key, val in status.items():
            if key.startswith("sync_") and isinstance(val, dict):
                source = key.replace("sync_", "")
                lines.append(f"\n### Synk: {source}")
                lines.append(f"- Sist synkronisert: {val.get('synced_at', 'Ukjent')}")
                lines.append(f"- Siste antall: {val.get('last_count', 0)}")

        return "\n".join(lines)

    # =========================================================================
    # Formatting helpers
    # =========================================================================

    @staticmethod
    def _format_case_summary(case: dict) -> str:
        """Format a case as a brief summary line."""
        sak_nr = case.get("sak_nr", "?")
        innklaget = case.get("innklaget", "")
        avgjoerelse = case.get("avgjoerelse", "")
        saken_gjelder = case.get("saken_gjelder", "")

        parts = [f"### {sak_nr}"]
        if innklaget:
            parts.append(f"**Innklaget:** {innklaget}")
        if avgjoerelse:
            parts.append(f"**Avgjørelse:** {avgjoerelse}")
        if saken_gjelder:
            parts.append(f"*{saken_gjelder}*")

        # Summary snippet
        summary = case.get("summary", "")
        if summary:
            snippet = summary[:200] + "..." if len(summary) > 200 else summary
            parts.append(snippet)

        parts.append("")  # blank line separator
        return "\n".join(parts)

    @staticmethod
    def _format_case_detail(case: dict) -> str:
        """Format a case with full detail."""
        sak_nr = case.get("sak_nr", "?")
        lines = [f"## KOFA {sak_nr}\n"]

        # Core fields
        field_labels = [
            ("innklaget", "Innklaget"),
            ("klager", "Klager"),
            ("sakstype", "Sakstype"),
            ("avgjoerelse", "Avgjørelse"),
            ("saken_gjelder", "Saken gjelder"),
            ("regelverk", "Regelverk"),
            ("konkurranseform", "Konkurranseform"),
            ("prosedyre", "Prosedyre"),
            ("avsluttet", "Avsluttet"),
        ]

        for field, label in field_labels:
            value = case.get(field)
            if value:
                lines.append(f"- **{label}:** {value}")

        # Summary
        summary = case.get("summary")
        if summary:
            lines.append(f"\n### Sammendrag\n{summary}")

        # PDF link
        pdf_url = case.get("pdf_url")
        if pdf_url:
            lines.append(f"\n**PDF:** {pdf_url}")

        # Page URL
        page_url = case.get("page_url")
        if page_url:
            lines.append(f"**Les mer:** {page_url}")

        return "\n".join(lines)

    @staticmethod
    def _format_decision_toc(sak_nr: str, paragraphs: list[dict]) -> str:
        """Format decision text as a table of contents with section stats."""
        # Group by section
        sections: dict[str, list[dict]] = {}
        for p in paragraphs:
            sec = p.get("section", "ukjent") or "ukjent"
            sections.setdefault(sec, []).append(p)

        total_chars = sum(len(p.get("text", "")) for p in paragraphs)
        total_tokens = total_chars // 4  # rough estimate

        lines = [f"## Avgjørelsestekst: {sak_nr}\n"]
        lines.append(f"**Totalt:** {len(paragraphs)} avsnitt (~{total_tokens:,} tokens)\n")

        # Display in logical order
        section_order = ["innledning", "bakgrunn", "anfoersler", "vurdering", "konklusjon", "raw"]
        ordered = [s for s in section_order if s in sections]
        for s in sections:
            if s not in ordered:
                ordered.append(s)

        section_labels = {
            "innledning": "Innledning",
            "bakgrunn": "Bakgrunn (faktum)",
            "anfoersler": "Partenes anførsler",
            "vurdering": "Klagenemndas vurdering",
            "konklusjon": "Konklusjon",
            "raw": "Ustrukturert tekst",
            "ukjent": "Ukjent seksjon",
        }

        for sec in ordered:
            paras = sections[sec]
            chars = sum(len(p.get("text", "")) for p in paras)
            tokens = chars // 4
            label = section_labels.get(sec, sec)
            lines.append(f"- **{label}:** {len(paras)} avsnitt (~{tokens:,} tokens)")

        lines.append("")
        lines.append(
            "Bruk `hent_avgjoerelse(sak_nr, seksjon='vurdering')` for å lese en bestemt seksjon."
        )

        return "\n".join(lines)

    @staticmethod
    def _format_decision_section(sak_nr: str, section: str, paragraphs: list[dict]) -> str:
        """Format decision text paragraphs for a specific section."""
        section_labels = {
            "innledning": "Innledning",
            "bakgrunn": "Bakgrunn (faktum)",
            "anfoersler": "Partenes anførsler",
            "vurdering": "Klagenemndas vurdering",
            "konklusjon": "Konklusjon",
            "raw": "Ustrukturert tekst",
        }
        label = section_labels.get(section, section)

        lines = [f"## {label}: {sak_nr}\n"]
        lines.append(f"{len(paragraphs)} avsnitt:\n")

        for p in paragraphs:
            num = p.get("paragraph_number", "?")
            text = p.get("text", "")
            lines.append(f"**({num})** {text}\n")

        return "\n".join(lines)
