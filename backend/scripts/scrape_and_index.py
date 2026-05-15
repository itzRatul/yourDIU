"""
Scrape & Index Script
=====================
One-time (or periodic) CLI script that:
  1. Scrapes all DIU seed URLs
  2. Chunks each page with the HybridChunker
  3. Embeds chunks with EmbeddingService
  4. Inserts docs + chunks into Supabase (diu_knowledge + document_chunks)

Usage:
    cd backend
    python scripts/scrape_and_index.py           # scrape + embed + store
    python scripts/scrape_and_index.py --local   # embed from data/processed/ (skip scraping)
    python scripts/scrape_and_index.py --dry-run # scrape only, no DB writes
"""

import asyncio
import logging
import sys
from pathlib import Path

# Make sure app/ is importable from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from app.core.supabase import supabase_admin
from app.services.scraper.diu_scraper import DIUScraper, ScrapedPage
from app.services.rag.chunking import HybridChunker
from app.services.rag.embeddings import EmbeddingService

logging.basicConfig(
    level=logging.WARNING,        # suppress verbose lib logs; Rich handles output
    format="%(levelname)s | %(name)s | %(message)s",
)
logger    = logging.getLogger("yourDIU.index")
console   = Console()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def upsert_knowledge(page: ScrapedPage) -> str | None:
    """Insert or update a page in diu_knowledge. Returns the row id."""
    try:
        resp = (
            supabase_admin.table("diu_knowledge")
            .upsert(
                {
                    "title":      page.title,
                    "content":    page.content,
                    "source_url": page.url,
                    "doc_type":   page.doc_type,
                    "metadata":   page.metadata,
                },
                on_conflict="source_url",
            )
            .execute()
        )
        return resp.data[0]["id"] if resp.data else None
    except Exception as exc:
        logger.error("DB upsert failed for %s: %s", page.url, exc)
        return None


def insert_chunks(chunks_data: list[dict]) -> int:
    """Batch-insert chunks into document_chunks. Returns count inserted."""
    if not chunks_data:
        return 0
    try:
        resp = supabase_admin.table("document_chunks").insert(chunks_data).execute()
        return len(resp.data or [])
    except Exception as exc:
        logger.error("Chunk insert failed: %s", exc)
        return 0


def delete_old_chunks(doc_id: str):
    """Remove existing chunks for a doc before re-indexing."""
    try:
        supabase_admin.table("document_chunks").delete().eq("doc_id", doc_id).execute()
    except Exception as exc:
        logger.warning("Could not delete old chunks for %s: %s", doc_id, exc)


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace):
    console.rule("[bold green]yourDIU — Scrape & Index Pipeline")

    scraper  = DIUScraper()
    chunker  = HybridChunker.get()
    embedder = EmbeddingService.get()

    # ── Step 1: Collect pages ───────────────────────────────────────────────
    if args.local:
        console.print("[cyan]Loading pages from data/processed/ (skip scraping)…")
        pages = scraper.load_processed()
    else:
        console.print("[cyan]Scraping DIU websites…")
        pages = await scraper.scrape_all()

    good_pages = [p for p in pages if p.success and p.content]
    console.print(f"[green]Pages ready: {len(good_pages)} / {len(pages)}")

    if not good_pages:
        console.print("[red]No usable pages. Exiting.")
        return

    if args.dry_run:
        console.print("[yellow]--dry-run: skipping embedding + DB writes.")
        _print_summary(good_pages)
        return

    # ── Step 2: Chunk ───────────────────────────────────────────────────────
    console.print("[cyan]Chunking pages…")
    all_docs_for_chunking = [
        {
            "text":       p.content,
            "source_url": p.url,
            "doc_type":   p.doc_type,
            "metadata":   p.metadata,
        }
        for p in good_pages
    ]
    raw_chunks = []
    for page in good_pages:
        chunks = chunker.chunk(
            text=page.content,
            source_url=page.url,
            doc_type=page.doc_type,
            extra_meta=page.metadata,
        )
        raw_chunks.append((page, chunks))

    total_chunks = sum(len(c) for _, c in raw_chunks)
    console.print(f"[green]Total chunks: {total_chunks}")

    # ── Step 3: Embed + Store ───────────────────────────────────────────────
    console.print("[cyan]Embedding & storing chunks…")

    stored_docs   = 0
    stored_chunks = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing pages", total=len(raw_chunks))

        for page, chunks in raw_chunks:
            if not chunks:
                progress.advance(task)
                continue

            # Upsert knowledge doc
            doc_id = upsert_knowledge(page)
            if not doc_id:
                progress.advance(task)
                continue
            stored_docs += 1

            # Remove stale chunks
            delete_old_chunks(doc_id)

            # Embed all chunk texts in one batch
            texts      = [c.text for c in chunks]
            embeddings = embedder.embed(texts)

            # Prepare rows
            rows = [
                {
                    "doc_id":      doc_id,
                    "chunk_text":  chunks[i].text,
                    "chunk_index": chunks[i].index,
                    "embedding":   embeddings[i],
                    "metadata":    chunks[i].metadata,
                }
                for i in range(len(chunks))
            ]

            n = insert_chunks(rows)
            stored_chunks += n
            progress.advance(task)

    # ── Summary ─────────────────────────────────────────────────────────────
    console.rule("[bold green]Done")
    console.print(f"[green]✓ Docs stored:   {stored_docs}")
    console.print(f"[green]✓ Chunks stored: {stored_chunks}")
    console.print(
        "\n[dim]Tip: create the IVFFlat index in Supabase SQL Editor after inserting data:\n"
        "  CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);"
    )


def _print_summary(pages: list[ScrapedPage]):
    table = Table(title="Scraped Pages", show_lines=True)
    table.add_column("Title",    style="cyan",  max_width=40)
    table.add_column("Type",     style="magenta")
    table.add_column("Chars",    justify="right")
    table.add_column("URL",      style="dim",   max_width=50)
    for p in pages:
        table.add_row(p.title, p.doc_type, str(len(p.content)), p.url)
    console.print(table)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape DIU websites and index into Supabase pgvector")
    parser.add_argument("--local",   action="store_true", help="Load from data/processed/ instead of scraping")
    parser.add_argument("--dry-run", action="store_true", help="Scrape only, skip DB writes")
    args = parser.parse_args()

    asyncio.run(run(args))
