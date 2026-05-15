"""
DIU Web Scraper
===============
Async scraper for Daffodil International University websites.
Uses httpx for HTTP + BeautifulSoup for parsing.
Saves raw HTML and clean extracted text to data/.
"""

import asyncio
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("yourDIU.scraper")

DATA_DIR = Path(__file__).resolve().parents[5] / "data"
RAW_DIR  = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"

# DIU pages to scrape — add more as needed
DIU_SEED_URLS: list[dict] = [
    # ── General ────────────────────────────────────────────────────────────
    {"url": "https://daffodilvarsity.edu.bd/",                           "doc_type": "general",    "title": "DIU Home"},
    {"url": "https://daffodilvarsity.edu.bd/about/about-diu",            "doc_type": "general",    "title": "About DIU"},
    {"url": "https://daffodilvarsity.edu.bd/contact",                    "doc_type": "general",    "title": "Contact DIU"},
    {"url": "https://daffodilvarsity.edu.bd/about/mission-vision",       "doc_type": "general",    "title": "Mission & Vision"},
    {"url": "https://daffodilvarsity.edu.bd/facilities",                 "doc_type": "general",    "title": "Facilities"},

    # ── Academic ───────────────────────────────────────────────────────────
    {"url": "https://daffodilvarsity.edu.bd/academic/academic-rules",    "doc_type": "academic",   "title": "Academic Rules"},
    {"url": "https://daffodilvarsity.edu.bd/academic/academic-calendar", "doc_type": "academic",   "title": "Academic Calendar"},
    {"url": "https://daffodilvarsity.edu.bd/academic/examination",       "doc_type": "academic",   "title": "Examination Rules"},
    {"url": "https://daffodilvarsity.edu.bd/academic/grading-system",    "doc_type": "academic",   "title": "Grading System"},

    # ── Admission ──────────────────────────────────────────────────────────
    {"url": "https://daffodilvarsity.edu.bd/admission/admission-policy", "doc_type": "academic",   "title": "Admission Policy"},
    {"url": "https://daffodilvarsity.edu.bd/admission/tuition-fees",     "doc_type": "academic",   "title": "Tuition Fees"},
    {"url": "https://daffodilvarsity.edu.bd/admission/scholarship",      "doc_type": "academic",   "title": "Scholarship"},

    # ── Departments ────────────────────────────────────────────────────────
    {"url": "https://daffodilvarsity.edu.bd/department/all-department",  "doc_type": "department", "title": "All Departments"},
    {"url": "https://daffodilvarsity.edu.bd/department/cse",             "doc_type": "department", "title": "CSE Department"},
    {"url": "https://daffodilvarsity.edu.bd/department/eee",             "doc_type": "department", "title": "EEE Department"},
    {"url": "https://daffodilvarsity.edu.bd/department/bba",             "doc_type": "department", "title": "BBA Department"},
    {"url": "https://daffodilvarsity.edu.bd/department/english",         "doc_type": "department", "title": "English Department"},
    {"url": "https://daffodilvarsity.edu.bd/department/pharmacy",        "doc_type": "department", "title": "Pharmacy Department"},
    {"url": "https://daffodilvarsity.edu.bd/department/law",             "doc_type": "department", "title": "Law Department"},

    # ── Research & Others ──────────────────────────────────────────────────
    {"url": "https://daffodilvarsity.edu.bd/research",                   "doc_type": "general",    "title": "Research"},
    {"url": "https://daffodilvarsity.edu.bd/library",                    "doc_type": "general",    "title": "Library"},
    {"url": "https://daffodilvarsity.edu.bd/news-events",                "doc_type": "event",      "title": "News & Events"},
]

# HTML tags whose content we always skip
_SKIP_TAGS = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "iframe"}

# CSS classes/ids that usually contain boilerplate
_SKIP_CLASSES = {"navbar", "nav", "footer", "header", "sidebar", "breadcrumb", "pagination", "cookie", "modal"}


@dataclass
class ScrapedPage:
    url:       str
    title:     str
    doc_type:  str
    content:   str                        # clean extracted text
    metadata:  dict = field(default_factory=dict)
    success:   bool = True
    error:     Optional[str] = None


def _clean_text(text: str) -> str:
    text = re.sub(r"\s{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _should_skip_tag(tag) -> bool:
    if tag.name in _SKIP_TAGS:
        return True
    classes = " ".join(tag.get("class", []))
    tag_id  = tag.get("id", "")
    combined = f"{classes} {tag_id}".lower()
    return any(skip in combined for skip in _SKIP_CLASSES)


def _extract_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(True):
        if _should_skip_tag(tag):
            tag.decompose()

    # Prefer <main> or <article>, fallback to <body>
    main = soup.find("main") or soup.find("article") or soup.find(id="main-content") or soup.body
    if not main:
        return ""

    lines = []
    for elem in main.descendants:
        if not hasattr(elem, "name"):          # NavigableString
            text = elem.strip()
            if text and len(text) > 2:
                lines.append(text)

    return _clean_text("\n".join(lines))


class DIUScraper:
    def __init__(self, delay: float = 1.5, timeout: int = 20):
        self.delay   = delay
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,bn;q=0.8",
        }
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        PROC_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Fetch helpers
    # ------------------------------------------------------------------

    def _page_id(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _save_raw(self, page_id: str, url: str, html: str):
        path = RAW_DIR / f"{page_id}.html"
        path.write_text(html, encoding="utf-8")
        logger.debug("Raw saved → %s", path.name)

    def _save_processed(self, page: ScrapedPage):
        page_id = self._page_id(page.url)
        path = PROC_DIR / f"{page_id}.json"
        path.write_text(json.dumps(asdict(page), ensure_ascii=False, indent=2), encoding="utf-8")
        logger.debug("Processed saved → %s", path.name)

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> Optional[str]:
        try:
            resp = await client.get(url, timeout=self.timeout, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            logger.warning("HTTP %d — %s", resp.status_code, url)
            return None
        except Exception as exc:
            logger.warning("Fetch failed — %s | %s", url, exc)
            return None

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def _parse(self, html: str, url: str, doc_type: str, hint_title: str) -> ScrapedPage:
        soup  = BeautifulSoup(html, "lxml")

        # Title: prefer <h1>, fallback to <title>
        h1    = soup.find("h1")
        title = (h1.get_text(strip=True) if h1 else None) or \
                (soup.title.string.strip() if soup.title else hint_title)

        content = _extract_text(soup)

        domain   = urlparse(url).netloc
        metadata = {"source_url": url, "domain": domain, "doc_type": doc_type}

        if not content or len(content) < 80:
            return ScrapedPage(url=url, title=title, doc_type=doc_type,
                               content="", metadata=metadata,
                               success=False, error="Insufficient content")

        return ScrapedPage(url=url, title=title, doc_type=doc_type,
                           content=content, metadata=metadata)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def scrape_one(self, client: httpx.AsyncClient, entry: dict) -> ScrapedPage:
        url      = entry["url"]
        doc_type = entry.get("doc_type", "general")
        title    = entry.get("title", url)

        logger.info("Scraping → %s", url)
        html = await self._fetch(client, url)

        if html is None:
            return ScrapedPage(url=url, title=title, doc_type=doc_type,
                               content="", metadata={},
                               success=False, error="Fetch failed")

        self._save_raw(self._page_id(url), url, html)
        page = self._parse(html, url, doc_type, title)
        if page.success:
            self._save_processed(page)
        return page

    async def scrape_all(self, urls: list[dict] = None) -> list[ScrapedPage]:
        """Scrape all seed URLs with rate-limit delay between requests."""
        targets = urls or DIU_SEED_URLS
        results: list[ScrapedPage] = []

        async with httpx.AsyncClient(headers=self.headers) as client:
            for entry in targets:
                page = await self.scrape_one(client, entry)
                results.append(page)
                ok  = "✓" if page.success else "✗"
                log = logger.info if page.success else logger.warning
                log("%s %s — %d chars", ok, page.url, len(page.content))
                await asyncio.sleep(self.delay)

        success = sum(1 for p in results if p.success)
        logger.info("Scraping complete: %d/%d pages succeeded", success, len(results))
        return results

    def load_processed(self) -> list[ScrapedPage]:
        """Load all previously scraped pages from data/processed/."""
        pages = []
        for path in sorted(PROC_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                pages.append(ScrapedPage(**data))
            except Exception as exc:
                logger.warning("Could not load %s: %s", path.name, exc)
        logger.info("Loaded %d processed pages from disk", len(pages))
        return pages
