"""
Supabase backend for KOFA MCP server.

Handles all database operations: upsert, search, sync from WP API and HTML scraping.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from kofa._supabase_utils import get_shared_client, with_retry
from kofa.scraper import KofaScraper, CaseMetadata

logger = logging.getLogger(__name__)

# WordPress REST API base
WP_API_BASE = "https://www.klagenemndssekretariatet.no/wp-json/wp/v2"

# HTML tag stripping pattern
HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities."""
    if not text:
        return ""
    clean = HTML_TAG_RE.sub("", text)
    return BeautifulSoup(clean, "html.parser").get_text(strip=True) if "&" in clean else clean.strip()


class KofaSupabaseBackend:
    """Supabase backend for KOFA data."""

    def __init__(self):
        self.client = get_shared_client()

    # =========================================================================
    # Read operations
    # =========================================================================

    @with_retry()
    def get_case(self, sak_nr: str) -> dict | None:
        """Get a single case by sak_nr."""
        result = (
            self.client.table("kofa_cases")
            .select("*")
            .eq("sak_nr", sak_nr)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    @with_retry()
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search using search_kofa() RPC function."""
        result = self.client.rpc(
            "search_kofa",
            {"search_query": query, "max_results": limit},
        ).execute()
        return result.data or []

    @with_retry()
    def recent_cases(
        self,
        limit: int = 20,
        sakstype: str | None = None,
        avgjoerelse: str | None = None,
        innklaget: str | None = None,
    ) -> list[dict]:
        """Get recent cases with optional filters."""
        query = self.client.table("kofa_cases").select("*")

        if sakstype:
            query = query.eq("sakstype", sakstype)
        if avgjoerelse:
            query = query.eq("avgjoerelse", avgjoerelse)
        if innklaget:
            query = query.ilike("innklaget", f"%{innklaget}%")

        query = query.order("avsluttet", desc=True).limit(limit)
        result = query.execute()
        return result.data or []

    @with_retry()
    def statistics(
        self,
        aar: int | None = None,
        gruppering: str = "avgjoerelse",
    ) -> list[dict]:
        """Get aggregate statistics."""
        result = self.client.rpc(
            "kofa_statistics",
            {"filter_year": aar, "group_by_field": gruppering},
        ).execute()
        return result.data or []

    @with_retry()
    def get_case_count(self) -> int:
        """Get total number of cases."""
        result = (
            self.client.table("kofa_cases")
            .select("*", count="exact")
            .limit(0)
            .execute()
        )
        return result.count or 0

    # =========================================================================
    # Write operations
    # =========================================================================

    @with_retry()
    def upsert_cases(self, cases: list[dict]) -> int:
        """Bulk upsert cases from WP API data."""
        if not cases:
            return 0
        self.client.table("kofa_cases").upsert(
            cases, on_conflict="sak_nr"
        ).execute()
        return len(cases)

    @with_retry()
    def update_case_metadata(self, sak_nr: str, metadata: dict) -> bool:
        """Update a case with scraped HTML metadata."""
        result = (
            self.client.table("kofa_cases")
            .update(metadata)
            .eq("sak_nr", sak_nr)
            .execute()
        )
        return bool(result.data)

    # =========================================================================
    # Sync: WordPress REST API
    # =========================================================================

    def sync_from_wp_api(self, force: bool = False) -> dict:
        """
        Sync all cases from KOFA WordPress REST API.

        Paginates through all cases, upserting into kofa_cases.
        Uses ?orderby=modified for incremental sync.

        Returns:
            dict with sync stats
        """
        stats = {"total": 0, "upserted": 0, "pages": 0, "errors": 0}

        # Get sync cursor for incremental sync
        cursor = None
        if not force:
            cursor = self._get_sync_cursor("wp_api")

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            page = 1
            per_page = 100

            while True:
                params = {
                    "per_page": per_page,
                    "page": page,
                    "orderby": "modified",
                    "order": "asc",
                    "_fields": "id,slug,title,excerpt,date,modified,link",
                }

                if cursor and not force:
                    params["modified_after"] = cursor

                try:
                    resp = client.get(f"{WP_API_BASE}/sak", params=params)
                    resp.raise_for_status()
                except httpx.HTTPError as e:
                    logger.error(f"WP API error on page {page}: {e}")
                    stats["errors"] += 1
                    break

                cases_data = resp.json()
                if not cases_data:
                    break

                # Transform WP API data to our schema
                batch = []
                latest_modified = cursor
                for item in cases_data:
                    sak_nr = _strip_html(item.get("title", {}).get("rendered", ""))
                    if not sak_nr:
                        continue

                    slug = item.get("slug", "")
                    page_url = item.get("link", "")
                    if not page_url and slug:
                        page_url = f"https://www.klagenemndssekretariatet.no/sak/{slug}"

                    summary = _strip_html(item.get("excerpt", {}).get("rendered", ""))

                    modified = item.get("modified", "")
                    published = item.get("date", "")

                    case_row = {
                        "sak_nr": sak_nr,
                        "slug": slug,
                        "page_url": page_url,
                        "summary": summary or None,
                        "wp_id": item.get("id"),
                        "wp_modified": modified or None,
                        "published": published or None,
                    }
                    batch.append(case_row)

                    if modified and (not latest_modified or modified > latest_modified):
                        latest_modified = modified

                # Deduplicate batch (WP API sometimes returns same sak_nr twice)
                seen = {}
                for case_row in batch:
                    seen[case_row["sak_nr"]] = case_row
                batch = list(seen.values())

                if batch:
                    try:
                        count = self.upsert_cases(batch)
                        stats["upserted"] += count
                    except Exception as e:
                        logger.error(f"Upsert error on page {page}: {e}")
                        stats["errors"] += 1

                stats["total"] += len(cases_data)
                stats["pages"] += 1

                # Check if we've reached the last page
                total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
                if page >= total_pages:
                    break

                page += 1
                time.sleep(0.5)  # Be polite

        # Update sync cursor
        if stats["upserted"] > 0:
            now = datetime.now(timezone.utc).isoformat()
            self._update_sync_cursor("wp_api", now, stats["upserted"])

        logger.info(
            f"WP API sync complete: {stats['upserted']} upserted "
            f"from {stats['pages']} pages ({stats['errors']} errors)"
        )
        return stats

    # =========================================================================
    # Sync: HTML scraping
    # =========================================================================

    def sync_html_metadata(self, limit: int | None = None) -> dict:
        """
        Scrape HTML metadata for cases that haven't been enriched yet.

        Only processes cases where innklaget IS NULL (not yet scraped).
        Resumable - safe to interrupt and restart.

        Args:
            limit: Max number of cases to scrape (None = all)

        Returns:
            dict with scrape stats
        """
        stats = {"scraped": 0, "errors": 0, "skipped": 0}

        # Find cases needing scraping
        query = (
            self.client.table("kofa_cases")
            .select("sak_nr, page_url")
            .is_("innklaget", "null")
            .order("sak_nr", desc=True)
        )
        if limit:
            query = query.limit(limit)

        result = query.execute()
        cases = result.data or []

        if not cases:
            logger.info("No cases need scraping")
            return stats

        logger.info(f"Scraping metadata for {len(cases)} cases")

        with KofaScraper() as scraper:
            for i, case in enumerate(cases):
                sak_nr = case["sak_nr"]
                url = case.get("page_url")

                if not url:
                    stats["skipped"] += 1
                    continue

                try:
                    meta = scraper.extract_metadata(url)
                    update = self._metadata_to_update(meta)
                    if update:
                        self.update_case_metadata(sak_nr, update)
                        stats["scraped"] += 1
                    else:
                        stats["skipped"] += 1
                except Exception as e:
                    logger.warning(f"Error scraping {sak_nr}: {e}")
                    stats["errors"] += 1

                # Progress logging every 50 cases
                if (i + 1) % 50 == 0:
                    logger.info(f"Progress: {i + 1}/{len(cases)} scraped")

                # Rate limit: be polite
                time.sleep(1.0)

        logger.info(
            f"HTML scrape complete: {stats['scraped']} scraped, "
            f"{stats['errors']} errors, {stats['skipped']} skipped"
        )
        return stats

    @staticmethod
    def _metadata_to_update(meta: CaseMetadata) -> dict:
        """Convert CaseMetadata to a dict for upsert (only non-None fields)."""
        update = {}
        if meta.innklaget:
            update["innklaget"] = meta.innklaget
        if meta.klager:
            update["klager"] = meta.klager
        if meta.sakstype:
            update["sakstype"] = meta.sakstype
        if meta.avgjoerelse:
            update["avgjoerelse"] = meta.avgjoerelse
        if meta.saken_gjelder:
            update["saken_gjelder"] = meta.saken_gjelder
        if meta.regelverk:
            update["regelverk"] = meta.regelverk
        if meta.konkurranseform:
            update["konkurranseform"] = meta.konkurranseform
        if meta.prosedyre:
            update["prosedyre"] = meta.prosedyre
        if meta.pdf_url:
            update["pdf_url"] = meta.pdf_url
        if meta.avsluttet_dato:
            update["avsluttet"] = meta.avsluttet_dato
        return update

    # =========================================================================
    # Sync metadata (cursors)
    # =========================================================================

    def _get_sync_cursor(self, source: str) -> str | None:
        """Get last sync cursor for a source."""
        try:
            result = (
                self.client.table("kofa_sync_meta")
                .select("cursor_value")
                .eq("source", source)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0].get("cursor_value")
        except Exception as e:
            logger.warning(f"Could not read sync cursor for {source}: {e}")
        return None

    def _update_sync_cursor(self, source: str, cursor: str, count: int) -> None:
        """Update sync cursor for a source."""
        try:
            self.client.table("kofa_sync_meta").upsert(
                {
                    "source": source,
                    "cursor_value": cursor,
                    "last_count": count,
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                },
                on_conflict="source",
            ).execute()
        except Exception as e:
            logger.warning(f"Could not update sync cursor for {source}: {e}")

    # =========================================================================
    # Status
    # =========================================================================

    def get_sync_status(self) -> dict:
        """Get sync status information."""
        status = {}

        # Case count
        try:
            count = self.get_case_count()
            status["cases"] = count
        except Exception:
            status["cases"] = 0

        # Enriched count (has innklaget)
        try:
            result = (
                self.client.table("kofa_cases")
                .select("*", count="exact")
                .not_.is_("innklaget", "null")
                .limit(0)
                .execute()
            )
            status["enriched"] = result.count or 0
        except Exception:
            status["enriched"] = 0

        # Sync cursors
        try:
            result = self.client.table("kofa_sync_meta").select("*").execute()
            for row in result.data or []:
                status[f"sync_{row['source']}"] = {
                    "synced_at": row.get("synced_at"),
                    "last_count": row.get("last_count"),
                    "cursor": row.get("cursor_value"),
                }
        except Exception:
            pass

        return status
