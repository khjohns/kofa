"""
Supabase backend for KOFA MCP server.

Handles all database operations: upsert, search, sync from WP API and HTML scraping.
"""

from __future__ import annotations

import logging
import re
import signal
import time
from datetime import UTC, datetime

import httpx
from bs4 import BeautifulSoup

from kofa._supabase_utils import _row, _rows, get_shared_client, with_retry
from kofa.scraper import CaseMetadata, KofaScraper

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
    return (
        BeautifulSoup(clean, "html.parser").get_text(strip=True) if "&" in clean else clean.strip()
    )


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
        result = self.client.table("kofa_cases").select("*").eq("sak_nr", sak_nr).limit(1).execute()
        return _row(result.data)

    @with_retry()
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search using search_kofa() RPC function."""
        result = self.client.rpc(
            "search_kofa",
            {"search_query": query, "max_results": limit},
        ).execute()
        return _rows(result.data)

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
        return _rows(result.data)

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
        return _rows(result.data)

    @with_retry()
    def get_case_count(self) -> int:
        """Get total number of cases."""
        result = (
            self.client.table("kofa_cases")
            .select("*", count="exact")  # type: ignore[arg-type]
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
        self.client.table("kofa_cases").upsert(cases, on_conflict="sak_nr").execute()
        return len(cases)

    @with_retry()
    def update_case_metadata(self, sak_nr: str, metadata: dict) -> bool:
        """Update a case with scraped HTML metadata."""
        result = self.client.table("kofa_cases").update(metadata).eq("sak_nr", sak_nr).execute()
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
            timeout=30.0,
            follow_redirects=True,
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
                log(
                    f"Page {page}/{total_pages} - {stats['upserted']} upserted ({rate:.0f} items/min)"
                )

                if page >= total_pages:
                    break

                page += 1
                time.sleep(0.5)

        # Update sync cursor
        if stats["upserted"] > 0:
            now = datetime.now(UTC).isoformat()
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
            # Find cases needing scraping (paginate to avoid PostgREST 1000-row limit)
            cases = []
            page_size = 1000
            offset = 0
            while True:
                query = self.client.table("kofa_cases").select("sak_nr, page_url")
                if refresh_pending:
                    query = query.not_.is_("scraped_at", "null").is_("avgjoerelse", "null")
                elif not force:
                    query = query.is_("scraped_at", "null")
                query = query.order("sak_nr", desc=True).range(offset, offset + page_size - 1)
                result = query.execute()
                batch = _rows(result.data)
                cases.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size

            if refresh_pending:
                log("Mode: refresh pending cases (scraped but no decision yet)")

            if limit:
                cases = cases[:limit]
            total = len(cases)

            if not cases:
                log("No cases need scraping")
                return stats

            log(
                f"Found {total} cases to scrape (delay={delay}s, max_time={max_time or 'unlimited'}min)"
            )
            if max_time:
                log(f"Will stop after {max_time} minutes")

            with KofaScraper() as scraper:
                for _i, case in enumerate(cases):
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
                            update["scraped_at"] = datetime.now(UTC).isoformat()
                            self.update_case_metadata(sak_nr, update)
                            stats["scraped"] += 1
                            consecutive_errors = 0
                            success = True
                            break
                        except httpx.TimeoutException:
                            if attempt < 2:
                                wait = 2 ** (attempt + 1)
                                logger.warning(
                                    f"Timeout scraping {sak_nr}, retry {attempt + 1}/3 in {wait}s"
                                )
                                time.sleep(wait)
                            else:
                                logger.warning(f"Timeout scraping {sak_nr} after 3 attempts")
                                stats["errors"] += 1
                                consecutive_errors += 1
                        except httpx.HTTPStatusError as e:
                            status_code = e.response.status_code
                            if status_code == 404:
                                # Page doesn't exist, mark as scraped to skip next time
                                self.update_case_metadata(
                                    sak_nr,
                                    {
                                        "scraped_at": datetime.now(UTC).isoformat(),
                                    },
                                )
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

        status_label = (
            "DONE" if not stats["stopped_reason"] else f"STOPPED ({stats['stopped_reason']})"
        )
        log(f"{status_label} in {elapsed / 60:.1f} min")
        log(f"Scraped: {stats['scraped']}, Errors: {stats['errors']}, Skipped: {stats['skipped']}")
        log(f"Rate: {rate:.0f}/min avg")
        if remaining > 0:
            log(f"Remaining: {remaining} cases")

        # Update sync cursor
        if stats["scraped"] > 0:
            self._update_sync_cursor(
                "html_scrape",
                datetime.now(UTC).isoformat(),
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
    # Sync: PDF text extraction
    # =========================================================================

    def sync_pdf_text(
        self,
        limit: int | None = None,
        max_time: int = 0,
        delay: float = 0.5,
        max_errors: int = 20,
        verbose: bool = False,
        force: bool = False,
    ) -> dict:
        """
        Download PDFs and extract structured decision text.

        Stores numbered paragraphs in kofa_decision_text table.
        Tracks extraction status via `pdf_extracted_at` column on kofa_cases.

        Args:
            limit: Max number of PDFs to process (None = all pending)
            max_time: Stop after N minutes (0 = unlimited)
            delay: Seconds between downloads (be polite)
            max_errors: Stop after N consecutive errors
            verbose: Print detailed progress to stdout
            force: Re-extract all PDFs, even previously extracted ones

        Returns:
            dict with extraction stats
        """
        from kofa.pdf_extractor import PdfExtractor

        global _shutdown_requested
        _shutdown_requested = False

        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _request_shutdown)
        signal.signal(signal.SIGTERM, _request_shutdown)

        stats = {
            "extracted": 0,
            "errors": 0,
            "skipped": 0,
            "total_paragraphs": 0,
            "stopped_reason": None,
        }
        start_time = time.time()
        consecutive_errors = 0
        log = _log if verbose else lambda msg: logger.info(msg)

        try:
            # Find cases with PDF URLs that haven't been extracted
            cases = []
            page_size = 1000
            offset = 0
            while True:
                query = (
                    self.client.table("kofa_cases")
                    .select("sak_nr, pdf_url")
                    .not_.is_("pdf_url", "null")
                )
                if not force:
                    query = query.is_("pdf_extracted_at", "null")
                query = query.order("sak_nr", desc=True).range(offset, offset + page_size - 1)
                result = query.execute()
                batch = _rows(result.data)
                cases.extend(batch)
                if len(batch) < page_size:
                    break
                offset += page_size

            if limit:
                cases = cases[:limit]
            total = len(cases)

            if not cases:
                log("No PDFs need extraction")
                return stats

            log(
                f"Found {total} PDFs to extract (delay={delay}s, max_time={max_time or 'unlimited'}min)"
            )

            extractor = PdfExtractor()

            for _i, case in enumerate(cases):
                if _shutdown_requested:
                    stats["stopped_reason"] = "interrupted"
                    log("Shutdown requested...")
                    break

                if max_time > 0:
                    elapsed_min = (time.time() - start_time) / 60
                    if elapsed_min >= max_time:
                        stats["stopped_reason"] = "time_limit"
                        log(f"Time limit reached ({max_time} min)")
                        break

                if consecutive_errors >= max_errors:
                    stats["stopped_reason"] = "too_many_errors"
                    log(f"Stopped: {max_errors} consecutive errors")
                    break

                sak_nr = case["sak_nr"]
                pdf_url = case["pdf_url"]

                # Extract with retry
                success = False
                for attempt in range(3):
                    try:
                        result = extractor.extract_from_url(pdf_url, sak_nr)

                        if not result.paragraphs:
                            logger.warning(f"{sak_nr}: No paragraphs extracted")
                            # Store raw text even without paragraphs (older prose format)
                            if result.raw_text:
                                self._store_decision_text(result)
                            self._mark_pdf_extracted(sak_nr)
                            stats["skipped"] += 1
                            consecutive_errors = 0
                            success = True
                            break

                        self._store_decision_text(result)
                        self._mark_pdf_extracted(sak_nr)
                        stats["extracted"] += 1
                        stats["total_paragraphs"] += result.paragraph_count
                        consecutive_errors = 0
                        success = True
                        break
                    except httpx.TimeoutException:
                        if attempt < 2:
                            wait = 2 ** (attempt + 1)
                            logger.warning(f"Timeout downloading {sak_nr}, retry in {wait}s")
                            time.sleep(wait)
                        else:
                            logger.warning(f"Timeout downloading {sak_nr} after 3 attempts")
                            stats["errors"] += 1
                            consecutive_errors += 1
                    except httpx.HTTPStatusError as e:
                        status_code = e.response.status_code
                        if status_code == 404:
                            self._mark_pdf_extracted(sak_nr)
                            stats["skipped"] += 1
                            consecutive_errors = 0
                            success = True
                            break
                        elif status_code in (429, 503):
                            wait = min(30, 5 * (attempt + 1))
                            logger.warning(f"HTTP {status_code} for {sak_nr}, waiting {wait}s")
                            time.sleep(wait)
                        else:
                            logger.warning(f"HTTP {status_code} downloading {sak_nr}")
                            stats["errors"] += 1
                            consecutive_errors += 1
                            break
                    except Exception as e:
                        logger.warning(f"Error extracting {sak_nr}: {e}")
                        stats["errors"] += 1
                        consecutive_errors += 1
                        break

                # Progress
                processed = stats["extracted"] + stats["errors"] + stats["skipped"]
                if processed > 0 and processed % 25 == 0:
                    elapsed_min = (time.time() - start_time) / 60
                    rate = processed / elapsed_min if elapsed_min > 0 else 0
                    remaining = total - processed
                    eta_min = remaining / rate if rate > 0 else 0
                    log(
                        f"Progress: {processed}/{total} "
                        f"({stats['extracted']} ok, {stats['errors']} err, {stats['skipped']} skip, "
                        f"{stats['total_paragraphs']} paras) "
                        f"| {rate:.0f}/min, ETA {eta_min:.0f} min"
                    )

                if success and delay > 0:
                    time.sleep(delay)

        finally:
            signal.signal(signal.SIGINT, prev_sigint)
            signal.signal(signal.SIGTERM, prev_sigterm)

        # Final summary
        elapsed = time.time() - start_time
        processed = stats["extracted"] + stats["errors"] + stats["skipped"]
        rate = processed / (elapsed / 60) if elapsed > 0 else 0

        status_label = (
            "DONE" if not stats["stopped_reason"] else f"STOPPED ({stats['stopped_reason']})"
        )
        log(f"{status_label} in {elapsed / 60:.1f} min")
        log(
            f"Extracted: {stats['extracted']}, Errors: {stats['errors']}, Skipped: {stats['skipped']}"
        )
        log(f"Total paragraphs: {stats['total_paragraphs']}, Rate: {rate:.0f}/min avg")

        if stats["extracted"] > 0:
            self._update_sync_cursor(
                "pdf_extract",
                datetime.now(UTC).isoformat(),
                stats["extracted"],
            )

        return stats

    def _store_decision_text(self, decision) -> None:
        """Store extracted decision text in kofa_decision_text table."""
        # Delete existing rows for this case (in case of re-extraction)
        self.client.table("kofa_decision_text").delete().eq("sak_nr", decision.sak_nr).execute()

        # Build rows from paragraphs (use sequential index as paragraph_number
        # since PDF numbering can restart per section and produce duplicates)
        rows = []
        for i, p in enumerate(decision.paragraphs):
            row = {
                "sak_nr": decision.sak_nr,
                "paragraph_number": i + 1,
                "section": p.section,
                "text": p.text,
            }
            # Store raw full text on first row only (for FTS)
            if i == 0:
                row["raw_full_text"] = decision.raw_text
            rows.append(row)

        # If no paragraphs but we have raw text, store a single row
        if not rows and decision.raw_text:
            rows.append(
                {
                    "sak_nr": decision.sak_nr,
                    "paragraph_number": 0,
                    "section": "raw",
                    "text": "",
                    "raw_full_text": decision.raw_text,
                }
            )

        # Batch insert (PostgREST handles up to ~1000 rows)
        if rows:
            self.client.table("kofa_decision_text").insert(rows).execute()

    def _mark_pdf_extracted(self, sak_nr: str) -> None:
        """Mark a case as having had its PDF extracted."""
        self.client.table("kofa_cases").update(
            {
                "pdf_extracted_at": datetime.now(UTC).isoformat(),
            }
        ).eq("sak_nr", sak_nr).execute()

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
            row = _row(result.data)
            if row:
                return row.get("cursor_value")
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
                    "synced_at": datetime.now(UTC).isoformat(),
                },
                on_conflict="source",
            ).execute()
        except Exception as e:
            logger.warning(f"Could not update sync cursor for {source}: {e}")

    # =========================================================================
    # Sync: Reference extraction
    # =========================================================================

    def sync_references(
        self,
        limit: int | None = None,
        verbose: bool = False,
        force: bool = False,
    ) -> dict:
        """
        Extract law and case references from decision text.

        Reads paragraphs from kofa_decision_text, runs regex extraction,
        deduplicates, detects regulation version (old/new), resolves
        lovdata_doc_id, and stores results.

        Args:
            limit: Max number of cases to process (None = all pending)
            verbose: Print progress to stdout
            force: Re-extract references for all cases

        Returns:
            dict with extraction stats
        """
        from kofa.reference_extractor import ReferenceExtractor, detect_regulation_version

        global _shutdown_requested
        _shutdown_requested = False

        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _request_shutdown)
        signal.signal(signal.SIGTERM, _request_shutdown)

        stats = {
            "cases_processed": 0,
            "law_refs": 0,
            "case_refs": 0,
            "eu_refs": 0,
            "court_refs": 0,
            "errors": 0,
            "stopped_reason": None,
        }
        start_time = time.time()
        log = _log if verbose else lambda msg: logger.info(msg)

        try:
            # Find cases with extracted text
            cases = self._find_cases_needing_references(force)

            if limit:
                cases = cases[:limit]
            total = len(cases)

            if not cases:
                log("No cases need reference extraction")
                return stats

            log(f"Found {total} cases for reference extraction")

            extractor = ReferenceExtractor()

            for sak_nr in cases:
                if _shutdown_requested:
                    stats["stopped_reason"] = "interrupted"
                    log("Shutdown requested...")
                    break

                try:
                    extractor.reset_context()
                    # Get all paragraphs for this case
                    paragraphs = self._get_decision_paragraphs(sak_nr)
                    if not paragraphs:
                        continue

                    all_law_refs = []
                    all_case_refs = []
                    all_eu_refs = []
                    all_court_refs = []

                    # Detect regulation version for this case
                    para_texts = [p.get("text", "") for p in paragraphs if p.get("text")]
                    reg_version = detect_regulation_version(para_texts, sak_nr)

                    for para in paragraphs:
                        text = para.get("text", "")
                        if not text:
                            continue
                        para_num = para.get("paragraph_number")
                        law_refs, case_refs, eu_refs, court_refs = extractor.extract_all(text)

                        # Attach paragraph number and context
                        for ref in law_refs:
                            all_law_refs.append(
                                {
                                    "sak_nr": sak_nr,
                                    "paragraph_number": para_num,
                                    "reference_type": ref.reference_type,
                                    "law_name": ref.law_name,
                                    "law_section": ref.section,
                                    "raw_text": ref.raw_text,
                                    "regulation_version": reg_version,
                                    "context": text[:300],
                                }
                            )

                        for ref in case_refs:
                            if ref.sak_nr == sak_nr:
                                continue  # Skip self-references
                            all_case_refs.append(
                                {
                                    "from_sak_nr": sak_nr,
                                    "to_sak_nr": ref.sak_nr,
                                    "paragraph_number": para_num,
                                    "context": text[:300],
                                }
                            )

                        for ref in eu_refs:
                            all_eu_refs.append(
                                {
                                    "sak_nr": sak_nr,
                                    "eu_case_id": ref.case_id,
                                    "eu_case_name": ref.case_name or None,
                                    "paragraph_number": para_num,
                                    "context": text[:300],
                                }
                            )

                        for ref in court_refs:
                            all_court_refs.append(
                                {
                                    "sak_nr": sak_nr,
                                    "court_case_id": ref.case_id,
                                    "court_level": ref.court_level,
                                    "court_name": ref.court_name,
                                    "paragraph_number": para_num,
                                    "context": text[:300],
                                    "raw_text": ref.raw_text,
                                }
                            )

                    # Deduplicate within case
                    all_law_refs = self._deduplicate_law_refs(all_law_refs)
                    all_case_refs = self._deduplicate_case_refs(all_case_refs)
                    all_eu_refs = self._deduplicate_eu_refs(all_eu_refs)
                    all_court_refs = self._deduplicate_court_refs(all_court_refs)

                    # Store
                    self._store_references(
                        sak_nr,
                        all_law_refs,
                        all_case_refs,
                        force,
                        all_eu_refs,
                        all_court_refs,
                    )

                    stats["cases_processed"] += 1
                    stats["law_refs"] += len(all_law_refs)
                    stats["case_refs"] += len(all_case_refs)
                    stats["eu_refs"] += len(all_eu_refs)
                    stats["court_refs"] += len(all_court_refs)

                except Exception as e:
                    logger.warning(f"Error extracting refs from {sak_nr}: {e}")
                    stats["errors"] += 1

                # Progress
                processed = stats["cases_processed"] + stats["errors"]
                if processed > 0 and processed % 50 == 0:
                    elapsed_min = (time.time() - start_time) / 60
                    rate = processed / elapsed_min if elapsed_min > 0 else 0
                    log(
                        f"Progress: {processed}/{total} "
                        f"({stats['law_refs']} law, {stats['case_refs']} case, "
                        f"{stats['eu_refs']} EU, {stats['court_refs']} court refs) "
                        f"| {rate:.0f}/min"
                    )

        finally:
            signal.signal(signal.SIGINT, prev_sigint)
            signal.signal(signal.SIGTERM, prev_sigterm)

        elapsed = time.time() - start_time
        status_label = (
            "DONE" if not stats["stopped_reason"] else f"STOPPED ({stats['stopped_reason']})"
        )
        log(f"{status_label} in {elapsed:.1f}s")
        log(
            f"Processed: {stats['cases_processed']}, "
            f"Law refs: {stats['law_refs']}, Case refs: {stats['case_refs']}, "
            f"EU refs: {stats['eu_refs']}, Court refs: {stats['court_refs']}, "
            f"Errors: {stats['errors']}"
        )

        if stats["cases_processed"] > 0:
            self._update_sync_cursor(
                "references",
                datetime.now(UTC).isoformat(),
                stats["cases_processed"],
            )

        return stats

    def _find_cases_needing_references(self, force: bool) -> list[str]:
        """Find cases with decision text that need reference extraction."""
        # Get all cases with decision text
        cases_with_text: list[str] = []
        page_size = 1000
        offset = 0
        while True:
            result = (
                self.client.table("kofa_decision_text")
                .select("sak_nr")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = _rows(result.data)
            cases_with_text.extend(r["sak_nr"] for r in batch)
            if len(batch) < page_size:
                break
            offset += page_size

        # Deduplicate (multiple paragraphs per case)
        unique_cases = sorted(set(cases_with_text))

        if force:
            return unique_cases

        # Exclude cases that already have references extracted
        already_extracted: set[str] = set()
        offset = 0
        while True:
            result = (
                self.client.table("kofa_law_references")
                .select("sak_nr")
                .limit(page_size)
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = _rows(result.data)
            already_extracted.update(r["sak_nr"] for r in batch)
            if len(batch) < page_size:
                break
            offset += page_size

        # Also check case_references and court_references
        for table, col in [
            ("kofa_case_references", "from_sak_nr"),
            ("kofa_court_references", "sak_nr"),
        ]:
            offset = 0
            while True:
                result = (
                    self.client.table(table)
                    .select(col)
                    .limit(page_size)
                    .range(offset, offset + page_size - 1)
                    .execute()
                )
                batch = _rows(result.data)
                already_extracted.update(r[col] for r in batch)
                if len(batch) < page_size:
                    break
                offset += page_size

        return [c for c in unique_cases if c not in already_extracted]

    def _get_decision_paragraphs(self, sak_nr: str) -> list[dict]:
        """Get all decision text paragraphs for a case."""
        result = (
            self.client.table("kofa_decision_text")
            .select("paragraph_number, section, text")
            .eq("sak_nr", sak_nr)
            .order("paragraph_number")
            .execute()
        )
        return _rows(result.data)

    @with_retry()
    def get_decision_text(self, sak_nr: str, section: str | None = None) -> list[dict]:
        """Get decision text paragraphs, optionally filtered by section."""
        query = (
            self.client.table("kofa_decision_text")
            .select("paragraph_number, section, text")
            .eq("sak_nr", sak_nr)
        )
        if section:
            query = query.eq("section", section)
        query = query.order("paragraph_number").limit(500)
        result = query.execute()
        return _rows(result.data)

    @staticmethod
    def _deduplicate_law_refs(refs: list[dict]) -> list[dict]:
        """Deduplicate law references within a case (keep first occurrence)."""
        seen: set[tuple[str, str]] = set()
        unique = []
        for ref in refs:
            key = (ref["law_name"], ref["law_section"])
            if key not in seen:
                seen.add(key)
                unique.append(ref)
        return unique

    @staticmethod
    def _deduplicate_case_refs(refs: list[dict]) -> list[dict]:
        """Deduplicate case references within a case."""
        seen: set[str] = set()
        unique = []
        for ref in refs:
            if ref["to_sak_nr"] not in seen:
                seen.add(ref["to_sak_nr"])
                unique.append(ref)
        return unique

    @staticmethod
    def _deduplicate_eu_refs(refs: list[dict]) -> list[dict]:
        """Deduplicate EU case references within a case, keeping longest name."""
        by_id: dict[str, dict] = {}
        for ref in refs:
            case_id = ref["eu_case_id"]
            if case_id not in by_id:
                by_id[case_id] = ref
            else:
                new_name = ref.get("eu_case_name") or ""
                old_name = by_id[case_id].get("eu_case_name") or ""
                if len(new_name) > len(old_name):
                    by_id[case_id]["eu_case_name"] = ref["eu_case_name"]
        return list(by_id.values())

    @staticmethod
    def _deduplicate_court_refs(refs: list[dict]) -> list[dict]:
        """Deduplicate court references within a case."""
        seen: set[str] = set()
        unique = []
        for ref in refs:
            if ref["court_case_id"] not in seen:
                seen.add(ref["court_case_id"])
                unique.append(ref)
        return unique

    def _store_references(
        self,
        sak_nr: str,
        law_refs: list[dict],
        case_refs: list[dict],
        force: bool,
        eu_refs: list[dict] | None = None,
        court_refs: list[dict] | None = None,
    ) -> None:
        """Store extracted references in database."""
        if force:
            # Delete existing references for this case
            self.client.table("kofa_law_references").delete().eq("sak_nr", sak_nr).execute()
            self.client.table("kofa_case_references").delete().eq("from_sak_nr", sak_nr).execute()
            self.client.table("kofa_eu_references").delete().eq("sak_nr", sak_nr).execute()
            self.client.table("kofa_court_references").delete().eq("sak_nr", sak_nr).execute()

        if law_refs:
            self.client.table("kofa_law_references").insert(law_refs).execute()
        if case_refs:
            self.client.table("kofa_case_references").insert(case_refs).execute()
        if eu_refs:
            self.client.table("kofa_eu_references").insert(eu_refs).execute()
        if court_refs:
            self.client.table("kofa_court_references").insert(court_refs).execute()

    # =========================================================================
    # Query: Find cases by law reference
    # =========================================================================

    _LAW_REF_SELECT = (
        "sak_nr, law_name, law_section, raw_text, context, regulation_version, "
        "kofa_cases(innklaget, avgjoerelse, saken_gjelder, avsluttet)"
    )

    @staticmethod
    def _section_filter(query, section: str):
        """Filter law_section by prefix: '16-10' matches '16-10', '16-10 (1)', etc."""
        return query.or_(f"law_section.eq.{section},law_section.like.{section} %")

    @with_retry()
    def find_by_law_reference(
        self,
        law_name: str,
        section: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """
        Find KOFA cases citing a specific law section.

        Args:
            law_name: Canonical law name (e.g. "anskaffelsesforskriften")
            section: Section number (e.g. "2-4") or None for all sections
            limit: Max results

        Returns:
            List of dicts with case info and reference context
        """
        query = (
            self.client.table("kofa_law_references")
            .select(self._LAW_REF_SELECT)
            .eq("law_name", law_name)
        )

        if section:
            query = self._section_filter(query, section)

        query = query.order("sak_nr", desc=True).limit(limit)
        result = query.execute()
        return _rows(result.data)

    @with_retry()
    def find_cases_by_sections(
        self,
        law_name: str,
        sections: list[str],
        limit: int = 20,
    ) -> list[dict]:
        """
        Find KOFA cases citing ALL specified sections of a law (AND semantics).

        Args:
            law_name: Canonical law name
            sections: Section numbers — cases must cite ALL of these
            limit: Max number of unique cases

        Returns:
            List of dicts with case info, grouped by sak_nr in caller
        """
        # Step 1: Get sak_nr sets per section, then intersect
        sak_nr_sets = []
        for section in sections:
            query = self._section_filter(
                self.client.table("kofa_law_references").select("sak_nr").eq("law_name", law_name),
                section,
            )
            result = query.execute()
            sak_nrs = {r["sak_nr"] for r in _rows(result.data)}
            sak_nr_sets.append(sak_nrs)

        if not sak_nr_sets:
            return []
        matching = sak_nr_sets[0]
        for s in sak_nr_sets[1:]:
            matching &= s
        if not matching:
            return []

        # Step 2: Fetch full details for matching cases (limit on unique cases)
        matching_list = sorted(matching, reverse=True)[:limit]
        # Build OR filter for all section prefixes
        section_clauses = ",".join(f"law_section.eq.{s},law_section.like.{s} %" for s in sections)
        result = (
            self.client.table("kofa_law_references")
            .select(self._LAW_REF_SELECT)
            .eq("law_name", law_name)
            .or_(section_clauses)
            .in_("sak_nr", matching_list)
            .order("sak_nr", desc=True)
            .execute()
        )
        return _rows(result.data)

    @with_retry()
    def count_cases_by_section(self, law_name: str, section: str) -> int:
        """Count references citing a law section (prefix match)."""
        q = (
            self.client.table("kofa_law_references")
            .select("sak_nr", count="exact")  # type: ignore[arg-type]
            .eq("law_name", law_name)
        )
        result = self._section_filter(q, section).limit(0).execute()
        return result.count or 0

    def find_related_cases(self, sak_nr: str) -> dict:
        """
        Find cases related to a given case via cross-references.

        Returns both cases that this case references (cites)
        and cases that reference this case (cited by).
        """
        # Cases this case cites (to_sak_nr has no FK, so fetch case info separately)
        cites_refs = (
            self.client.table("kofa_case_references")
            .select("to_sak_nr")
            .eq("from_sak_nr", sak_nr)
            .execute()
        )
        cited_nrs = list({r["to_sak_nr"] for r in _rows(cites_refs.data)})

        cites = []
        if cited_nrs:
            cases_result = (
                self.client.table("kofa_cases")
                .select("sak_nr, innklaget, avgjoerelse, saken_gjelder, avsluttet")
                .in_("sak_nr", cited_nrs)
                .order("sak_nr")
                .execute()
            )
            cites = _rows(cases_result.data)
            # Add cases not in DB (older cases we don't have)
            found = {c["sak_nr"] for c in cites}
            for nr in sorted(cited_nrs):
                if nr not in found:
                    cites.append({"sak_nr": nr})

        # Cases that cite this case (from_sak_nr has FK, can use join)
        cited_by_result = (
            self.client.table("kofa_case_references")
            .select(
                "from_sak_nr, "
                "kofa_cases!kofa_case_references_from_sak_nr_fkey("
                "innklaget, avgjoerelse, saken_gjelder, avsluttet)"
            )
            .eq("to_sak_nr", sak_nr)
            .order("from_sak_nr", desc=True)
            .execute()
        )
        # Flatten: merge from_sak_nr with joined case info, dedup
        seen = set()
        cited_by = []
        for r in _rows(cited_by_result.data):
            nr = r["from_sak_nr"]
            if nr in seen:
                continue
            seen.add(nr)
            case_info = r.get("kofa_cases", {}) or {}
            cited_by.append({"sak_nr": nr, **case_info})

        return {
            "sak_nr": sak_nr,
            "cites": cites,
            "cited_by": cited_by,
        }

    def most_cited_cases(self, limit: int = 20) -> list[dict]:
        """
        Find the most frequently cited KOFA cases.

        Uses a raw SQL query via RPC since PostgREST doesn't support
        GROUP BY with COUNT easily.
        """
        result = self.client.rpc(
            "kofa_most_cited",
            {"max_results": limit},
        ).execute()
        return _rows(result.data)

    # =========================================================================
    # Sync: EU case law (EUR-Lex)
    # =========================================================================

    def sync_eu_case_law(
        self,
        limit: int | None = None,
        delay: float = 10.0,
        max_errors: int = 20,
        verbose: bool = False,
        force: bool = False,
    ) -> dict:
        """
        Fetch EU Court judgment text from EUR-Lex for cases referenced in KOFA.

        Finds EU case IDs in kofa_eu_references that are missing from
        kofa_eu_case_law, then fetches full text from EUR-Lex HTML.

        Args:
            limit: Max number of judgments to fetch (None = all missing)
            delay: Seconds between requests (EUR-Lex robots.txt: 10s)
            max_errors: Stop after N consecutive errors
            verbose: Print progress to stdout
            force: Re-fetch all, even previously fetched

        Returns:
            dict with fetch stats
        """
        from kofa.eurlex_fetcher import EurLexFetcher

        global _shutdown_requested
        _shutdown_requested = False

        prev_sigint = signal.getsignal(signal.SIGINT)
        prev_sigterm = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGINT, _request_shutdown)
        signal.signal(signal.SIGTERM, _request_shutdown)

        stats = {
            "fetched": 0,
            "errors": 0,
            "skipped": 0,
            "stopped_reason": None,
        }
        start_time = time.time()
        consecutive_errors = 0
        log = _log if verbose else lambda msg: logger.info(msg)

        try:
            # Find EU case IDs referenced in KOFA decisions
            missing = self._find_missing_eu_case_law(force)

            if limit:
                missing = missing[:limit]
            total = len(missing)

            if not missing:
                log("No EU judgments need fetching")
                return stats

            log(f"Found {total} EU judgments to fetch (delay={delay}s)")

            fetcher = EurLexFetcher()

            for _i, eu_case_id in enumerate(missing):
                if _shutdown_requested:
                    stats["stopped_reason"] = "interrupted"
                    log("Shutdown requested...")
                    break

                if consecutive_errors >= max_errors:
                    stats["stopped_reason"] = "too_many_errors"
                    log(f"Stopped: {max_errors} consecutive errors")
                    break

                try:
                    judgment = fetcher.fetch(eu_case_id)

                    if judgment is None:
                        stats["skipped"] += 1
                        consecutive_errors = 0
                    else:
                        self._upsert_eu_case_law(judgment)
                        stats["fetched"] += 1
                        consecutive_errors = 0

                except Exception as e:
                    logger.warning(f"Error fetching {eu_case_id}: {e}")
                    stats["errors"] += 1
                    consecutive_errors += 1

                # Progress
                processed = stats["fetched"] + stats["errors"] + stats["skipped"]
                if processed > 0 and processed % 10 == 0:
                    elapsed_min = (time.time() - start_time) / 60
                    rate = processed / elapsed_min if elapsed_min > 0 else 0
                    remaining = total - processed
                    eta_min = remaining / rate if rate > 0 else 0
                    log(
                        f"Progress: {processed}/{total} "
                        f"({stats['fetched']} ok, {stats['errors']} err, "
                        f"{stats['skipped']} skip) "
                        f"| {rate:.0f}/min, ETA {eta_min:.0f} min"
                    )

                if delay > 0:
                    time.sleep(delay)

        finally:
            signal.signal(signal.SIGINT, prev_sigint)
            signal.signal(signal.SIGTERM, prev_sigterm)

        # Final summary
        elapsed = time.time() - start_time
        status_label = (
            "DONE" if not stats["stopped_reason"] else f"STOPPED ({stats['stopped_reason']})"
        )
        log(f"{status_label} in {elapsed / 60:.1f} min")
        log(f"Fetched: {stats['fetched']}, Errors: {stats['errors']}, Skipped: {stats['skipped']}")

        if stats["fetched"] > 0:
            self._update_sync_cursor(
                "eu_case_law",
                datetime.now(UTC).isoformat(),
                stats["fetched"],
            )

        return stats

    def _find_missing_eu_case_law(self, force: bool) -> list[str]:
        """Find EU case IDs referenced in KOFA but not yet in kofa_eu_case_law."""
        # Get all unique eu_case_id from kofa_eu_references
        referenced: set[str] = set()
        page_size = 1000
        offset = 0
        while True:
            result = (
                self.client.table("kofa_eu_references")
                .select("eu_case_id")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = _rows(result.data)
            referenced.update(r["eu_case_id"] for r in batch)
            if len(batch) < page_size:
                break
            offset += page_size

        if force:
            return sorted(referenced)

        # Get already fetched
        already_fetched: set[str] = set()
        offset = 0
        while True:
            result = (
                self.client.table("kofa_eu_case_law")
                .select("eu_case_id")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            batch = _rows(result.data)
            already_fetched.update(r["eu_case_id"] for r in batch)
            if len(batch) < page_size:
                break
            offset += page_size

        return sorted(referenced - already_fetched)

    def _upsert_eu_case_law(self, judgment) -> None:
        """Upsert a fetched EU judgment into kofa_eu_case_law."""
        row = {
            "eu_case_id": judgment.eu_case_id,
            "celex": judgment.celex,
            "case_name": judgment.case_name or None,
            "judgment_date": judgment.judgment_date or None,
            "subject": judgment.subject or None,
            "description": judgment.description or None,
            "full_text": judgment.full_text,
            "source_url": judgment.source_url,
            "language": judgment.language,
        }
        self.client.table("kofa_eu_case_law").upsert(row, on_conflict="eu_case_id").execute()

    @with_retry()
    def get_eu_case_law(self, eu_case_id: str) -> dict | None:
        """Get a single EU judgment by case ID."""
        result = (
            self.client.table("kofa_eu_case_law")
            .select("*")
            .eq("eu_case_id", eu_case_id)
            .limit(1)
            .execute()
        )
        return _row(result.data)

    # =========================================================================
    # Query: EU case references
    # =========================================================================

    @with_retry()
    def find_by_eu_case(self, eu_case_id: str, limit: int = 20) -> list[dict]:
        """Find KOFA cases citing a specific EU Court case."""
        result = (
            self.client.table("kofa_eu_references")
            .select(
                "sak_nr, eu_case_id, eu_case_name, context, "
                "kofa_cases(innklaget, avgjoerelse, saken_gjelder, avsluttet)"
            )
            .eq("eu_case_id", eu_case_id)
            .order("sak_nr", desc=True)
            .limit(limit)
            .execute()
        )
        return _rows(result.data)

    @with_retry()
    def most_cited_eu_cases(self, limit: int = 20) -> list[dict]:
        """Find the most frequently cited EU Court cases in KOFA decisions."""
        result = self.client.rpc(
            "kofa_most_cited_eu",
            {"max_results": limit},
        ).execute()
        return _rows(result.data)

    # =========================================================================
    # Decision text search (FTS)
    # =========================================================================

    @with_retry()
    def search_decision_text(
        self,
        query: str,
        section: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Full-text search on decision text paragraphs via RPC."""
        result = self.client.rpc(
            "search_kofa_decision_text",
            {
                "search_query": query,
                "section_filter": section,
                "max_results": limit,
            },
        ).execute()
        return _rows(result.data)

    # =========================================================================
    # Forarbeider (legislative preparatory works)
    # =========================================================================

    @with_retry()
    def get_forarbeide(self, doc_id: str) -> dict | None:
        """Get a forarbeider document by doc_id."""
        result = (
            self.client.table("kofa_forarbeider")
            .select("*")
            .eq("doc_id", doc_id)
            .limit(1)
            .execute()
        )
        return _row(result.data)

    @with_retry()
    def list_forarbeider(self) -> list[dict]:
        """List all forarbeider documents."""
        result = self.client.table("kofa_forarbeider").select("*").order("doc_id").execute()
        return _rows(result.data)

    @with_retry()
    def get_forarbeider_sections(
        self,
        doc_id: str,
        section_number: str | None = None,
    ) -> list[dict]:
        """
        Get sections for a forarbeider document.

        If section_number is provided, matches on prefix: "4.1" returns
        4.1, 4.1.1, 4.1.2 etc.
        """
        query = (
            self.client.table("kofa_forarbeider_sections")
            .select("section_number, title, level, page_start, sort_order, text, char_count")
            .eq("doc_id", doc_id)
        )
        if section_number:
            # Prefix match: "4.1" matches "4.1", "4.1.1", "4.1.2"
            query = query.or_(
                f"section_number.eq.{section_number},section_number.like.{section_number}.%"
            )
        query = query.order("sort_order").limit(500)
        result = query.execute()
        return _rows(result.data)

    def upsert_forarbeider(self, doc_data: dict) -> None:
        """Upsert a forarbeider document metadata."""
        self.client.table("kofa_forarbeider").upsert(doc_data, on_conflict="doc_id").execute()

    def upsert_forarbeider_sections(self, doc_id: str, sections: list[dict]) -> int:
        """Replace all sections for a forarbeider document."""
        # Delete existing sections
        self.client.table("kofa_forarbeider_sections").delete().eq("doc_id", doc_id).execute()

        # Batch insert (chunks of 500 to stay under PostgREST limits)
        inserted = 0
        for i in range(0, len(sections), 500):
            batch = sections[i : i + 500]
            self.client.table("kofa_forarbeider_sections").insert(batch).execute()
            inserted += len(batch)

        return inserted

    @with_retry()
    def search_forarbeider(
        self, query: str, doc_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Full-text search on forarbeider sections via RPC."""
        result = self.client.rpc(
            "search_kofa_forarbeider",
            {
                "search_query": query,
                "doc_filter": doc_id,
                "max_results": limit,
            },
        ).execute()
        return _rows(result.data)

    def sync_forarbeider(
        self,
        pdf_dir: str,
        force: bool = False,
        verbose: bool = False,
    ) -> dict:
        """
        Import forarbeider PDFs from a directory into the database.

        Reads all known PDFs from pdf_dir, extracts sections via TOC,
        and upserts into kofa_forarbeider + kofa_forarbeider_sections.
        """
        from pathlib import Path

        from kofa.forarbeider_extractor import (
            FORARBEIDER_REGISTRY,
            ForarbeiderExtractor,
        )

        stats: dict[str, int] = {"documents": 0, "sections": 0, "errors": 0}
        log = _log if verbose else lambda msg: logger.info(msg)
        pdf_path = Path(pdf_dir)

        extractor = ForarbeiderExtractor()

        for filename in sorted(FORARBEIDER_REGISTRY.keys()):
            filepath = pdf_path / filename
            if not filepath.exists():
                log(f"Ikke funnet: {filename}")
                stats["errors"] += 1
                continue

            try:
                doc = extractor.extract(filepath)

                # Check if already imported (skip if not force)
                if not force:
                    existing = self.get_forarbeide(doc.doc_id)
                    if existing and existing.get("section_count", 0) == doc.section_count:
                        log(f"Allerede importert: {doc.title} ({doc.section_count} seksjoner)")
                        continue

                # Upsert document metadata
                doc_data = {
                    "doc_id": doc.doc_id,
                    "doc_type": doc.doc_type,
                    "title": doc.title,
                    "full_title": doc.full_title,
                    "session": doc.session,
                    "page_count": doc.page_count,
                    "char_count": doc.char_count,
                    "section_count": doc.section_count,
                    "source_file": doc.source_file,
                }
                self.upsert_forarbeider(doc_data)

                # Build section rows
                section_rows = []
                for s in doc.sections:
                    section_rows.append(
                        {
                            "doc_id": doc.doc_id,
                            "section_number": s.section_number,
                            "title": s.title,
                            "level": s.level,
                            "page_start": s.page_start,
                            "parent_path": s.parent_path,
                            "sort_order": s.sort_order,
                            "text": s.text,
                        }
                    )

                inserted = self.upsert_forarbeider_sections(doc.doc_id, section_rows)
                stats["documents"] += 1
                stats["sections"] += inserted

                non_empty = sum(1 for s in doc.sections if s.text.strip())
                log(
                    f"Importert: {doc.title} — {inserted} seksjoner "
                    f"({non_empty} med tekst, {doc.char_count:,} tegn)"
                )

            except Exception as e:
                logger.error(f"Feil ved import av {filename}: {e}")
                stats["errors"] += 1

        log(
            f"Ferdig: {stats['documents']} dokumenter, "
            f"{stats['sections']} seksjoner, {stats['errors']} feil"
        )

        return stats

    def sync_forarbeider_references(
        self,
        force: bool = False,
        verbose: bool = False,
    ) -> dict:
        """Extract law and EU references from forarbeider section text."""
        from kofa.reference_extractor import ReferenceExtractor

        stats: dict[str, int] = {
            "documents": 0,
            "law_refs": 0,
            "eu_refs": 0,
            "errors": 0,
        }
        log = _log if verbose else lambda msg: logger.info(msg)

        # Get all forarbeider documents
        docs = self.list_forarbeider()
        if not docs:
            log("No forarbeider documents found")
            return stats

        extractor = ReferenceExtractor()

        for doc in docs:
            doc_id = doc["doc_id"]
            try:
                # Check if already extracted (skip if refs exist and not force)
                if not force:
                    existing = (
                        self.client.table("kofa_forarbeider_law_refs")
                        .select("id", count="exact")  # type: ignore[arg-type]
                        .eq("doc_id", doc_id)
                        .limit(1)
                        .execute()
                    )
                    if existing.count and existing.count > 0:
                        log(f"Allerede ekstrahert: {doc_id}")
                        continue

                # Get all sections with text
                sections = self.get_forarbeider_sections(doc_id)
                if not sections:
                    continue

                all_law_refs = []
                all_eu_refs = []

                for section in sections:
                    text = section.get("text", "")
                    if not text or len(text) < 20:
                        continue

                    section_number = section.get("section_number", "")
                    extractor.reset_context()

                    law_refs = extractor.extract_law_references(text)
                    eu_refs = extractor.extract_eu_references(text)

                    for ref in law_refs:
                        all_law_refs.append(
                            {
                                "doc_id": doc_id,
                                "section_number": section_number,
                                "law_name": ref.law_name,
                                "law_section": ref.section,
                                "context": text[:300],
                            }
                        )

                    for ref in eu_refs:
                        all_eu_refs.append(
                            {
                                "doc_id": doc_id,
                                "section_number": section_number,
                                "eu_case_id": ref.case_id,
                                "context": text[:300],
                            }
                        )

                # Deduplicate within document (same law_name+law_section per section)
                seen_law: set[tuple[str, str, str]] = set()
                unique_law_refs = []
                for ref in all_law_refs:
                    key = (ref["section_number"], ref["law_name"], ref["law_section"])
                    if key not in seen_law:
                        seen_law.add(key)
                        unique_law_refs.append(ref)

                seen_eu: set[tuple[str, str]] = set()
                unique_eu_refs = []
                for ref in all_eu_refs:
                    key = (ref["section_number"], ref["eu_case_id"])
                    if key not in seen_eu:
                        seen_eu.add(key)
                        unique_eu_refs.append(ref)

                # Delete existing refs for this doc (in case of re-run)
                self.client.table("kofa_forarbeider_law_refs").delete().eq(
                    "doc_id", doc_id
                ).execute()
                self.client.table("kofa_forarbeider_eu_refs").delete().eq(
                    "doc_id", doc_id
                ).execute()

                # Insert in batches
                if unique_law_refs:
                    for i in range(0, len(unique_law_refs), 500):
                        batch = unique_law_refs[i : i + 500]
                        self.client.table("kofa_forarbeider_law_refs").insert(batch).execute()

                if unique_eu_refs:
                    for i in range(0, len(unique_eu_refs), 500):
                        batch = unique_eu_refs[i : i + 500]
                        self.client.table("kofa_forarbeider_eu_refs").insert(batch).execute()

                stats["documents"] += 1
                stats["law_refs"] += len(unique_law_refs)
                stats["eu_refs"] += len(unique_eu_refs)

                log(
                    f"Referanser: {doc_id} — "
                    f"{len(unique_law_refs)} lovhenvisninger, "
                    f"{len(unique_eu_refs)} EU-referanser"
                )

            except Exception as e:
                logger.error(f"Feil ved referanseekstraksjon for {doc_id}: {e}")
                stats["errors"] += 1

        return stats

    @with_retry()
    def find_forarbeider_by_law_reference(
        self,
        law_name: str,
        section: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        """Find forarbeider sections citing a specific law section."""
        query = (
            self.client.table("kofa_forarbeider_law_refs")
            .select(
                "doc_id, section_number, law_name, law_section, context, kofa_forarbeider(title)"
            )
            .eq("law_name", law_name)
        )

        if section:
            query = query.eq("law_section", section)

        query = query.order("doc_id").limit(limit)
        result = query.execute()
        return _rows(result.data)

    # =========================================================================
    # Status
    # =========================================================================

    def get_sync_status(self) -> dict:
        """Get sync status information including pipeline coverage."""
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
                .select(
                    "*",
                    count="exact",  # type: ignore[arg-type]
                )
                .not_.is_("innklaget", "null")
                .limit(0)
                .execute()
            )
            status["enriched"] = result.count or 0
        except Exception:
            status["enriched"] = 0

        # Pipeline coverage counts
        try:
            status["pipeline"] = self._get_pipeline_stats()
        except Exception as e:
            logger.debug(f"Could not fetch pipeline stats: {e}")

        # Sync cursors
        try:
            result = self.client.table("kofa_sync_meta").select("*").execute()
            for row in _rows(result.data):
                status[f"sync_{row['source']}"] = {
                    "synced_at": row.get("synced_at"),
                    "last_count": row.get("last_count"),
                    "cursor": row.get("cursor_value"),
                }
        except Exception:
            pass

        return status

    def _get_pipeline_stats(self) -> dict:
        """Get pipeline coverage counts for status display."""

        def _exact_count(table: str, not_null_col: str | None = None, neq: tuple | None = None):
            q = (
                self.client.table(table)
                .select("*", count="exact")  # type: ignore[arg-type]
                .limit(0)
            )
            if not_null_col:
                q = q.not_.is_(not_null_col, "null")
            if neq:
                q = q.neq(neq[0], neq[1])
            return q.execute().count or 0

        def _distinct_count(table: str, col: str = "sak_nr", neq: tuple | None = None) -> int:
            unique: set[str] = set()
            page_size = 1000
            offset = 0
            while True:
                q = self.client.table(table).select(col)
                if neq:
                    q = q.neq(neq[0], neq[1])
                result = q.range(offset, offset + page_size - 1).execute()
                batch = _rows(result.data)
                unique.update(r[col] for r in batch)
                if len(batch) < page_size:
                    break
                offset += page_size
            return len(unique)

        have_pdf_url = _exact_count("kofa_cases", not_null_col="pdf_url")
        have_text = _distinct_count("kofa_decision_text")
        sectioned = _distinct_count("kofa_decision_text", neq=("section", "raw"))
        law_ref_cases = _distinct_count("kofa_law_references")
        case_ref_cases = _distinct_count("kofa_case_references", col="from_sak_nr")
        eu_ref_cases = _distinct_count("kofa_eu_references")
        court_ref_cases = _distinct_count("kofa_court_references")
        eu_case_law_count = _exact_count("kofa_eu_case_law")
        total_paragraphs = _exact_count("kofa_decision_text", neq=("section", "raw"))
        embeddings = _exact_count("kofa_decision_text", not_null_col="embedding")

        return {
            "have_pdf_url": have_pdf_url,
            "have_text": have_text,
            "sectioned": sectioned,
            "raw_only": have_text - sectioned,
            "law_ref_cases": law_ref_cases,
            "case_ref_cases": case_ref_cases,
            "eu_ref_cases": eu_ref_cases,
            "court_ref_cases": court_ref_cases,
            "eu_case_law_count": eu_case_law_count,
            "embeddings": embeddings,
            "total_paragraphs": total_paragraphs,
        }
