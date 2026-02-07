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
        limit: int = 20,
    ) -> str:
        """Find KOFA cases citing a specific law section."""
        from kofa.reference_extractor import LAW_ALIASES

        # Normalize law name
        canonical = LAW_ALIASES.get(lov.lower().strip())
        if not canonical:
            # Try as-is (user may already pass canonical name)
            canonical = lov.lower().strip()

        results = self.backend.find_by_law_reference(canonical, paragraf, limit)

        if not results:
            section_label = f" {paragraf}" if paragraf else ""
            return f"Ingen KOFA-saker funnet som refererer til {lov} {section_label}".strip()

        section_label = f" {paragraf}" if paragraf else ""
        lines = [f"## KOFA-praksis: {lov} {section_label}\n".strip()]
        lines.append(f"Fant {len(results)} saker:\n")

        for r in results:
            sak_nr = r.get("sak_nr", "?")
            law_section = r.get("law_section", "")
            case_info = r.get("kofa_cases", {}) or {}
            innklaget = case_info.get("innklaget", "")
            avgjoerelse = case_info.get("avgjoerelse", "")
            saken_gjelder = case_info.get("saken_gjelder", "")
            avsluttet = case_info.get("avsluttet", "")

            reg_version = r.get("regulation_version", "")
            version_label = " (gammel forskrift)" if reg_version == "old" else ""

            parts = [f"### {sak_nr}{version_label}"]
            if law_section:
                parts.append(f"**Referert paragraf:** {law_section}")
            if innklaget:
                parts.append(f"**Innklaget:** {innklaget}")
            if avgjoerelse:
                parts.append(f"**Avgjoerelse:** {avgjoerelse}")
            if saken_gjelder:
                parts.append(f"*{saken_gjelder}*")
            if avsluttet:
                parts.append(f"Avsluttet: {avsluttet}")

            context = r.get("context", "")
            if context:
                snippet = context[:200] + "..." if len(context) > 200 else context
                parts.append(f"> {snippet}")

            parts.append("")
            lines.append("\n".join(parts))

        return "\n".join(lines)

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
        lines.append(f"Basert på kryssreferanser i avgjørelsestekst (2020+).\n")

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

        # WP API sync (skip if only doing PDF or reference extraction)
        if not pdf and not references:
            wp_stats = self.backend.sync_from_wp_api(force=force, verbose=verbose)
            lines.append(f"### WordPress API")
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
            lines.append(f"\n### HTML-skraping")
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
            lines.append(f"\n### PDF-ekstraksjon")
            lines.append(f"- Ekstrahert **{pdf_stats['extracted']}** avgjørelser ({pdf_stats['total_paragraphs']} avsnitt)")
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
            lines.append(f"\n### Referanse-ekstraksjon")
            lines.append(
                f"- Prosessert **{ref_stats['cases_processed']}** saker "
                f"({ref_stats['law_refs']} lovhenvisninger, {ref_stats['case_refs']} sakskryssreferanser, "
                f"{ref_stats.get('eu_refs', 0)} EU-referanser)"
            )
            if ref_stats["errors"]:
                lines.append(f"- {ref_stats['errors']} feil")
            if ref_stats.get("stopped_reason"):
                lines.append(f"- Stoppet: {ref_stats['stopped_reason']}")

        return "\n".join(lines)

    def get_status(self) -> str:
        """Get sync status."""
        status = self.backend.get_sync_status()

        if not status or status.get("cases", 0) == 0:
            return """## KOFA Status

**Status:** Ikke synkronisert

Kjør `sync()` for å laste ned saker fra KOFA."""

        lines = ["## KOFA Status\n"]
        lines.append(f"- **Totalt saker:** {status.get('cases', 0)}")
        lines.append(f"- **Beriket (med metadata):** {status.get('enriched', 0)}")

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
