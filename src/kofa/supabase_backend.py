"""
Supabase backend for KOFA MCP server.

Handles all database operations: upsert, search, sync from WP API and HTML scraping.
"""

from __future__ import annotations

import logging
import re
import signal
import time
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from kofa._supabase_utils import get_shared_client, with_retry
from kofa.scraper import KofaScraper, CaseMetadata

logger = logging.getLogger(__name__)

# Graceful shutdown flag
_shutdown_requested = False


def _request_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True


def _log(msg: str):
    """Print with timestamp (for CLI sync scripts)."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

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

    def sync_from_wp_api(self, force: bool = False, verbose: bool = False) -> dict:
        """
        Sync all cases from KOFA WordPress REST API.

        Paginates through all cases, upserting into kofa_cases.
        Uses ?orderby=modified&modified_after=<cursor> for incremental sync.

        Args:
            force: Ignore cursor, re-fetch everything
            verbose: Print progress to stdout

        Returns:
            dict with sync stats
        """
        global _shutdown_requested
        _shutdown_requested = False

        stats = {"total": 0, "upserted": 0, "pages": 0, "errors": 0}
        start_time = time.time()
        log = _log if verbose else lambda msg: logger.info(msg)

        # Get sync cursor for incremental sync
        cursor = None
        if not force:
            cursor = self._get_sync_cursor("wp_api")
            if cursor:
                log(f"Incremental sync from cursor: {cursor}")
            else:
                log("No cursor found, doing full sync")
        else:
            log("Force mode: full re-sync")

        # First request to get total count
        with httpx.Client(
            timeout=30.0, follow_redirects=True,
            headers={"User-Agent": "kofa-mcp/0.1.0"},
        ) as client:
            page = 1
            per_page = 100
            total_items = None

            while not _shutdown_requested:
                params = {
                    "per_page": per_page,
                    "page": page,
                    "orderby": "modified",
                    "order": "asc",
                    "_fields": "id,slug,title,excerpt,date,modified,link",
                }

                if cursor and not force:
                    params["modified_after"] = cursor

                # Fetch with retry
                resp = None
                for attempt in range(3):
                    try:
                        resp = client.get(f"{WP_API_BASE}/sak", params=params)
                        resp.raise_for_status()
                        break
                    except httpx.HTTPError as e:
                        if attempt == 2:
                            logger.error(f"WP API error on page {page} (3 attempts): {e}")
                            stats["errors"] += 1
                            resp = None
                            break
                        wait = 2 ** (attempt + 1)
                        logger.warning(f"WP API error page {page}, retrying in {wait}s: {e}")
                        time.sleep(wait)

                if resp is None:
                    break

                # Get total from first response
                if total_items is None:
                    total_items = int(resp.headers.get("X-WP-Total", "0"))
                    total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
                    log(f"WP API: {total_items} cases across {total_pages} pages")

                cases_data = resp.json()
                if not cases_data:
                    break

                # Transform WP API data to our schema
                batch = []
                for item in cases_data:
                    sak_nr = _strip_html(item.get("title", {}).get("rendered", ""))
                    if not sak_nr:
                        continue

                    slug = item.get("slug", "")
                    page_url = item.get("link", "")
                    if not page_url and slug:
                        page_url = f"https://www.klagenemndssekretariatet.no/sak/{slug}"

                    summary = _strip_html(item.get("excerpt", {}).get("rendered", ""))

                    case_row = {
                        "sak_nr": sak_nr,
                        "slug": slug,
                        "page_url": page_url,
                        "summary": summary or None,
                        "wp_id": item.get("id"),
                        "wp_modified": item.get("modified") or None,
                        "published": item.get("date") or None,
                    }
                    batch.append(case_row)

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

                # Progress
                elapsed = time.time() - start_time
                rate = stats["total"] / (elapsed / 60) if elapsed > 0 else 0
                total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
                log(f"Page {page}/{total_pages} - {stats['upserted']} upserted ({rate:.0f} items/min)")

                if page >= total_pages:
                    break

                page += 1
                time.sleep(0.5)

        # Update sync cursor
        if stats["upserted"] > 0:
            now = datetime.now(timezone.utc).isoformat()
            self._update_sync_cursor("wp_api", now, stats["upserted"])

        elapsed = time.time() - start_time
        status = "STOPPED" if _shutdown_requested else "DONE"
        log(
            f"{status} in {elapsed:.0f}s: {stats['upserted']} upserted "
            f"from {stats['pages']} pages ({stats['errors']} errors)"
        )
        return stats

    # =========================================================================
    # Sync: HTML scraping
    # =========================================================================

    def sync_html_metadata(
        self,
        limit: int | None = None,
        max_time: int = 0,
        delay: float = 1.0,
        max_errors: int = 20,
        verbose: bool = False,
        force: bool = False,
        refresh_pending: bool = False,
    ) -> dict:
        """
        Scrape HTML metadata for cases not yet scraped.

        Tracks scrape status via `scraped_at` column. Only processes cases
        where scraped_at IS NULL (never scraped). Resumable and safe to
        interrupt with Ctrl+C.

        Args:
            limit: Max number of cases to scrape (None = all pending)
            max_time: Stop after N minutes (0 = unlimited)
            delay: Seconds between requests (be polite to server)
            max_errors: Stop after N consecutive errors (server might be down)
            force: Re-scrape all cases, even previously scraped ones
            verbose: Print detailed progress to stdout
            refresh_pending: Re-scrape cases that were scraped but have no
                decision yet (avgjoerelse IS NULL AND scraped_at IS NOT NULL)

        Returns:
            dict with scrape stats
        """
        global _shutdown_requested
        _shutdown_requested = False

        # Install signal handlers for graceful shutdown
        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _request_shutdown)
        signal.signal(signal.SIGTERM, _request_shutdown)

        stats = {
            "scraped": 0,
            "errors": 0,
            "skipped": 0,
            "stopped_reason": None,
        }
        start_time = time.time()
        consecutive_errors = 0
        log = _log if verbose else lambda msg: logger.info(msg)

        try:
            # Find cases needing scraping
            query = self.client.table("kofa_cases").select("sak_nr, page_url")
            if refresh_pending:
                # Re-scrape previously scraped cases that have no decision yet
                query = query.not_.is_("scraped_at", "null").is_("avgjoerelse", "null")
                log("Mode: refresh pending cases (scraped but no decision yet)")
            elif not force:
                query = query.is_("scraped_at", "null")
            query = query.order("sak_nr", desc=True)
            if limit:
                query = query.limit(limit)

            result = query.execute()
            cases = result.data or []
            total = len(cases)

            if not cases:
                log("No cases need scraping")
                return stats

            log(f"Found {total} cases to scrape (delay={delay}s, max_time={max_time or 'unlimited'}min)")
            if max_time:
                log(f"Will stop after {max_time} minutes")

            with KofaScraper() as scraper:
                for i, case in enumerate(cases):
                    # --- Check stop conditions ---
                    if _shutdown_requested:
                        stats["stopped_reason"] = "interrupted"
                        log("Shutdown requested, finishing current batch...")
                        break

                    if max_time > 0:
                        elapsed_min = (time.time() - start_time) / 60
                        if elapsed_min >= max_time:
                            stats["stopped_reason"] = "time_limit"
                            log(f"Time limit reached ({max_time} min)")
                            break

                    if consecutive_errors >= max_errors:
                        stats["stopped_reason"] = "too_many_errors"
                        log(f"Stopped: {max_errors} consecutive errors (server issue?)")
                        break

                    sak_nr = case["sak_nr"]
                    url = case.get("page_url")

                    if not url:
                        stats["skipped"] += 1
                        continue

                    # --- Scrape with retry ---
                    success = False
                    for attempt in range(3):
                        try:
                            meta = scraper.extract_metadata(url)
                            update = self._metadata_to_update(meta)
                            update["scraped_at"] = datetime.now(timezone.utc).isoformat()
                            self.update_case_metadata(sak_nr, update)
                            stats["scraped"] += 1
                            consecutive_errors = 0
                            success = True
                            break
                        except httpx.TimeoutException:
                            if attempt < 2:
                                wait = 2 ** (attempt + 1)
                                logger.warning(f"Timeout scraping {sak_nr}, retry {attempt + 1}/3 in {wait}s")
                                time.sleep(wait)
                            else:
                                logger.warning(f"Timeout scraping {sak_nr} after 3 attempts")
                                stats["errors"] += 1
                                consecutive_errors += 1
                        except httpx.HTTPStatusError as e:
                            status_code = e.response.status_code
                            if status_code == 404:
                                # Page doesn't exist, mark as scraped to skip next time
                                self.update_case_metadata(sak_nr, {
                                    "scraped_at": datetime.now(timezone.utc).isoformat(),
                                })
                                stats["skipped"] += 1
                                consecutive_errors = 0
                                success = True
                                break
                            elif status_code in (429, 503):
                                wait = min(30, 5 * (attempt + 1))
                                logger.warning(f"HTTP {status_code} for {sak_nr}, waiting {wait}s")
                                time.sleep(wait)
                            else:
                                logger.warning(f"HTTP {status_code} scraping {sak_nr}: {e}")
                                stats["errors"] += 1
                                consecutive_errors += 1
                                break
                        except Exception as e:
                            logger.warning(f"Error scraping {sak_nr}: {e}")
                            stats["errors"] += 1
                            consecutive_errors += 1
                            break

                    # --- Progress ---
                    processed = stats["scraped"] + stats["errors"] + stats["skipped"]
                    if processed > 0 and processed % 25 == 0:
                        elapsed_min = (time.time() - start_time) / 60
                        rate = processed / elapsed_min if elapsed_min > 0 else 0
                        remaining = total - processed
                        eta_min = remaining / rate if rate > 0 else 0
                        log(
                            f"Progress: {processed}/{total} "
                            f"({stats['scraped']} ok, {stats['errors']} err, {stats['skipped']} skip) "
                            f"| {rate:.0f}/min, ETA {eta_min:.0f} min"
                        )

                    # Rate limit
                    if success and delay > 0:
                        time.sleep(delay)

        finally:
            # Restore original signal handlers
            signal.signal(signal.SIGINT, prev_sigint)
            signal.signal(signal.SIGTERM, prev_sigterm)

        # Final summary
        elapsed = time.time() - start_time
        processed = stats["scraped"] + stats["errors"] + stats["skipped"]
        rate = processed / (elapsed / 60) if elapsed > 0 else 0
        remaining = total - processed

        status_label = "DONE" if not stats["stopped_reason"] else f"STOPPED ({stats['stopped_reason']})"
        log(f"{status_label} in {elapsed / 60:.1f} min")
        log(f"Scraped: {stats['scraped']}, Errors: {stats['errors']}, Skipped: {stats['skipped']}")
        log(f"Rate: {rate:.0f}/min avg")
        if remaining > 0:
            log(f"Remaining: {remaining} cases")

        # Update sync cursor
        if stats["scraped"] > 0:
            self._update_sync_cursor(
                "html_scrape",
                datetime.now(timezone.utc).isoformat(),
                stats["scraped"],
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
