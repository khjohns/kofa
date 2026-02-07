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

    def sync(
        self,
        scrape: bool = False,
        pdf: bool = False,
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

        # WP API sync (skip if only doing PDF extraction)
        if not pdf:
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
