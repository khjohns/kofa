#!/usr/bin/env python3
"""
Generate embeddings for KOFA decision text paragraphs using Gemini API.

Usage:
    python scripts/embed_kofa.py --dry-run      # Verify count and cost first
    python scripts/embed_kofa.py                # Run embedding generation
    python scripts/embed_kofa.py --workers 3    # Parallel processing
    python scripts/embed_kofa.py --max-time 25  # Stop after 25 minutes
    python scripts/embed_kofa.py --force        # Re-embed all (ignore content_hash)

Recommended for Supabase free/micro tier:
    python scripts/embed_kofa.py --workers 1 --max-time 25
"""

import argparse
import hashlib
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add src to path for kofa imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from google import genai
from google.genai import types
from supabase import create_client

# Configuration
EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100  # Google API batch limit
TASK_TYPE_DOCUMENT = "RETRIEVAL_DOCUMENT"

# Global Gemini client (thread-safe for reads)
_genai_client = None
_genai_lock = threading.Lock()

# Thread-local Supabase clients
_thread_local = threading.local()


def log(msg: str):
    """Print message with timestamp."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def get_supabase_client():
    """Create Supabase client (one per thread for thread safety)."""
    if hasattr(_thread_local, "supabase_client"):
        return _thread_local.supabase_client

    url = os.environ.get("SUPABASE_URL")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    _thread_local.supabase_client = create_client(url, key)
    return _thread_local.supabase_client


def get_gemini_client() -> genai.Client:
    """Get or create Gemini API client (thread-safe singleton)."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    with _genai_lock:
        if _genai_client is not None:
            return _genai_client

        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY must be set")
        _genai_client = genai.Client(api_key=api_key)
        return _genai_client


def content_hash(text: str) -> str:
    """Generate hash of content for change tracking."""
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def normalize_embedding(embedding: list[float]) -> list[float]:
    """Normalize embedding to unit length for correct cosine similarity."""
    norm = math.sqrt(sum(x * x for x in embedding))
    if norm == 0:
        return embedding
    return [x / norm for x in embedding]


def create_embedding_text(sak_nr: str, section: str, text: str) -> str:
    """
    Enrich paragraph with context for better embedding quality.

    Includes case number and section type to provide semantic context.
    """
    section_labels = {
        "innledning": "Innledning",
        "bakgrunn": "Bakgrunn",
        "anfoersler": "Partenes anfoersler",
        "vurdering": "Klagenemndas vurdering",
        "konklusjon": "Konklusjon",
    }
    label = section_labels.get(section, section or "")
    return f"KOFA sak {sak_nr} — {label}\n\n{text}"


def fetch_paragraphs_needing_embedding(supabase, force: bool = False, batch_size: int = 1000):
    """Fetch paragraphs that need embedding. Yields batches."""
    offset = 0
    while True:
        query = supabase.table("kofa_decision_text").select(
            "id, sak_nr, section, text, content_hash"
        )
        if not force:
            query = query.is_("embedding", "null")
        # Skip raw_full_text rows (section='raw' with very long text) and empty paragraphs
        query = query.neq("section", "raw").gt("text", "")
        query = query.range(offset, offset + batch_size - 1)
        result = query.execute()

        if not result.data:
            break

        yield result.data
        offset += batch_size

        if len(result.data) < batch_size:
            break


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts."""
    client = get_gemini_client()
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=texts,
        config=types.EmbedContentConfig(
            task_type=TASK_TYPE_DOCUMENT,
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return [normalize_embedding(list(emb.values)) for emb in result.embeddings]


def update_embeddings(supabase, updates: list[dict], max_retries: int = 3) -> int:
    """Update embeddings one by one with retry logic."""
    success = 0
    for update in updates:
        for attempt in range(max_retries):
            try:
                supabase.table("kofa_decision_text").update(
                    {"embedding": update["embedding"], "content_hash": update["content_hash"]}
                ).eq("id", update["id"]).execute()
                success += 1
                break
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
    return success


def process_batch(batch_texts: list[str], batch_ids: list[str]) -> int:
    """Process a single batch: generate embeddings and update database."""
    supabase = get_supabase_client()

    try:
        embeddings = generate_embeddings_batch(batch_texts)
    except Exception as e:
        print(f"    [ERROR] Embedding generation failed: {e}")
        return 0

    updates = []
    for para_id, embedding, text in zip(batch_ids, embeddings, batch_texts, strict=False):
        updates.append({"id": para_id, "embedding": embedding, "content_hash": content_hash(text)})

    return update_embeddings(supabase, updates)


def main():
    parser = argparse.ArgumentParser(
        description="Generate KOFA decision text embeddings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/embed_kofa.py --dry-run
    python scripts/embed_kofa.py --limit 100
    python scripts/embed_kofa.py --workers 3
    python scripts/embed_kofa.py --workers 1 --max-time 25
        """,
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE, help=f"Batch size (default: {BATCH_SIZE})"
    )
    parser.add_argument("--limit", type=int, help="Max paragraphs to process")
    parser.add_argument("--workers", type=int, default=1, help="Parallel workers (default: 1)")
    parser.add_argument("--delay", type=float, default=0, help="Delay between batches (seconds)")
    parser.add_argument(
        "--max-time", type=int, default=0, help="Stop after N minutes (0=unlimited)"
    )
    parser.add_argument("--force", action="store_true", help="Re-embed all (ignore content_hash)")
    args = parser.parse_args()

    log("Initializing clients...")
    supabase = get_supabase_client()

    if not args.dry_run:
        get_gemini_client()

    total_processed = 0
    total_tokens = 0
    start_time = time.time()

    log("Fetching paragraphs needing embedding...")

    # Collect all items to process
    all_items = []
    for batch in fetch_paragraphs_needing_embedding(supabase, force=args.force):
        for para in batch:
            if args.limit and len(all_items) >= args.limit:
                break
            text = create_embedding_text(para["sak_nr"], para.get("section", ""), para["text"])
            all_items.append({"id": para["id"], "text": text})
            total_tokens += len(text) // 4
        if args.limit and len(all_items) >= args.limit:
            break

    log(f"Found {len(all_items):,} paragraphs to embed")

    stopped_early = False

    if args.dry_run:
        log(f"[DRY RUN] Would process {len(all_items):,} paragraphs")
        log(f"Estimated tokens: ~{total_tokens:,} (${total_tokens * 0.15 / 1_000_000:.2f})")
        total_processed = len(all_items)
    else:
        # Split into sub-batches
        sub_batches = []
        for i in range(0, len(all_items), args.batch_size):
            batch_slice = all_items[i : i + args.batch_size]
            batch_texts = [b["text"] for b in batch_slice]
            batch_ids = [b["id"] for b in batch_slice]
            sub_batches.append((batch_texts, batch_ids))

        log(f"Total: {len(all_items):,} paragraphs in {len(sub_batches)} batches")

        try:
            if args.workers > 1:
                with ThreadPoolExecutor(max_workers=args.workers) as executor:
                    futures = {
                        executor.submit(process_batch, texts, ids): (texts, ids)
                        for texts, ids in sub_batches
                    }
                    for future in as_completed(futures):
                        if args.max_time > 0:
                            elapsed_min = (time.time() - start_time) / 60
                            if elapsed_min >= args.max_time:
                                log(f"Time limit reached ({args.max_time} min)")
                                executor.shutdown(wait=False, cancel_futures=True)
                                stopped_early = True
                                break
                        try:
                            successful = future.result()
                            total_processed += successful
                            elapsed_min = (time.time() - start_time) / 60
                            rate = total_processed / elapsed_min if elapsed_min > 0 else 0
                            remaining = len(all_items) - total_processed
                            eta_min = remaining / rate if rate > 0 else 0
                            log(
                                f"Processed {total_processed:,} / {len(all_items):,} "
                                f"({rate:.0f}/min, ETA {eta_min:.0f} min)"
                            )
                        except Exception as e:
                            log(f"[ERROR] Batch failed: {e}")
                        if args.delay > 0:
                            time.sleep(args.delay)
            else:
                for batch_texts, batch_ids in sub_batches:
                    if args.max_time > 0:
                        elapsed_min = (time.time() - start_time) / 60
                        if elapsed_min >= args.max_time:
                            log(f"Time limit reached ({args.max_time} min)")
                            stopped_early = True
                            break

                    successful = process_batch(batch_texts, batch_ids)
                    total_processed += successful
                    elapsed_min = (time.time() - start_time) / 60
                    rate = total_processed / elapsed_min if elapsed_min > 0 else 0
                    remaining = len(all_items) - total_processed
                    eta_min = remaining / rate if rate > 0 else 0
                    log(
                        f"Processed {total_processed:,} / {len(all_items):,} "
                        f"({rate:.0f}/min, ETA {eta_min:.0f} min)"
                    )
                    if args.delay > 0:
                        time.sleep(args.delay)

        except KeyboardInterrupt:
            log("Interrupted by user (Ctrl+C)")
            stopped_early = True

    elapsed = time.time() - start_time
    rate = total_processed / (elapsed / 60) if elapsed > 0 else 0

    print("")
    log(f"{'STOPPED' if stopped_early else 'DONE'} in {elapsed / 60:.1f} minutes")
    log(f"Processed: {total_processed:,} paragraphs ({rate:.0f}/min avg)")
    if stopped_early:
        remaining = len(all_items) - total_processed
        log(f"Remaining: {remaining:,} paragraphs")
    log(f"Tokens used: ~{total_tokens:,} (${total_tokens * 0.15 / 1_000_000:.2f})")


if __name__ == "__main__":
    main()
