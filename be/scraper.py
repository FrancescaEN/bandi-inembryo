import asyncio
import hashlib
import re
from datetime import date, datetime

import httpx
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.async_api import async_playwright

from sources import SOURCES


ITALIAN_MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}


# =========================
# UTILS
# =========================
def clean(text):
    return " ".join(text.split()) if text else ""


def extract_dates(text):
    patterns = [
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{4}-\d{2}-\d{2}",
    ]

    dates = []

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            try:
                d = date_parser.parse(match.group(0), dayfirst=True)
                dates.append(d)
            except:
                pass

    return sorted(dates)


def extract_textual_dates(text):
    pattern = re.compile(
        r"\b(\d{1,2})\s+"
        r"(gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
        r"\s+(\d{4})\b",
        re.IGNORECASE,
    )

    dates = []

    for match in pattern.finditer(text):
        try:
            day = int(match.group(1))
            month = ITALIAN_MONTHS[match.group(2).lower()]
            year = int(match.group(3))
            dates.append(datetime(year, month, day))
        except ValueError:
            pass

    return dates


def extract_deadline(text):
    deadline_patterns = [
        re.compile(
            r"(?:scadenza|deadline|entro\s+il)[:\s-]*"
            r"(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
            re.IGNORECASE,
        ),
        re.compile(
            r"(?:scadenza|deadline|entro\s+il)[:\s-]*"
            r"(\d{1,2}\s+"
            r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
            r"\s+\d{4})",
            re.IGNORECASE,
        ),
    ]

    for pattern in deadline_patterns:
        match = pattern.search(text)
        if not match:
            continue

        candidates = extract_dates(match.group(1)) + extract_textual_dates(match.group(1))
        if candidates:
            return sorted(candidates)[-1]

    return None


def parse_iso_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


# =========================
# PIPELINE
# =========================
class Pipeline:

    def __init__(self):
        self.semaphore = asyncio.Semaphore(5)

    # =========================
    # FILTER KEYWORDS
    # =========================
    def matches_filters(self, source, text):

        text = text.lower()

        for group in source.get("required_keyword_groups", []):
            if not any(k in text for k in group):
                return False

        return True

    # =========================
    # FILTER BANDI ATTIVI
    # =========================
    def is_active(self, deadline_str):

        if not deadline_str:
            return True  # mantieni se non disponibile

        deadline = parse_iso_date(deadline_str)
        if not deadline:
            return True

        return deadline >= date.today()

    # =========================
    # RUN
    # =========================
    async def run(self):

        results = []

        async with httpx.AsyncClient(timeout=20) as client:

            for source in SOURCES:

                if not source["enabled"]:
                    continue

                if source["mode"] == "rss":
                    results += await self.fetch_rss(source)

                elif source["mode"] == "playwright":
                    results += await self.fetch_playwright(source)

                elif source["mode"] == "html":
                    results += await self.fetch_html(client, source)

        return self.deduplicate(results)

    # =========================
    # RSS
    # =========================
    async def fetch_rss(self, source):

        print(f"Scraping {source['name']} (RSS)")

        feed = feedparser.parse(source["url"])

        results = []

        for entry in feed.entries:

            text = f"{entry.title} {getattr(entry, 'summary', '')}"

            if not self.matches_filters(source, text):
                continue

            try:
                published = datetime(*entry.published_parsed[:6])
            except:
                published = None

            results.append({
                "title": entry.title,
                "url": entry.link,
                "summary": entry.summary,
                "ente": "Commissione Europea",
                "published_at": published.strftime("%Y-%m-%d") if published else None,
                "deadline": None,
                "source": source["name"],
                "hash": hashlib.sha1(entry.link.encode()).hexdigest(),
            })

        return results

    # =========================
    # HTML
    # =========================
    async def fetch_html(self, client, source):

        print(f"Scraping {source['name']}")

        try:
            res = await client.get(source["url"])
            res.raise_for_status()
        except:
            return []

        soup = BeautifulSoup(res.text, "html.parser")

        results = []

        for a in soup.find_all("a", href=True):

            title = clean(a.get_text())
            href = a["href"]

            if not title or len(title) < 20:
                continue

            if not href.startswith("http"):
                continue

            if not self.matches_filters(source, title):
                continue

            results.append({
                "title": title,
                "url": href,
                "summary": title,
                "ente": source["name"],
                "published_at": None,
                "deadline": None,
                "source": source["name"],
                "hash": hashlib.sha1(href.encode()).hexdigest(),
            })

        return results

    # =========================
    # PLAYWRIGHT
    # =========================
    async def fetch_playwright(self, source):

        print(f"Scraping {source['name']} (Playwright)")

        results = []

        async with async_playwright() as p:

            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(source["url"])
            await page.wait_for_timeout(4000)

            html = await page.content()
            soup = BeautifulSoup(html, "html.parser")

            links = []

            for a in soup.find_all("a", href=True):

                href = a["href"]

                if not href.startswith("http"):
                    continue

                if len(href) < 40:
                    continue

                links.append(href)

            links = list(set(links))[:25]

            print("LINK TROVATI:", len(links))

            tasks = [
                self.parse_detail(browser, source, url)
                for url in links
            ]

            pages = await asyncio.gather(*tasks)

            for p in pages:
                if p:
                    results.append(p)

            await browser.close()

        return results

    # =========================
    # DETAIL
    # =========================
    async def parse_detail(self, browser, source, url):

        async with self.semaphore:

            page = await browser.new_page()

            try:
                await page.goto(url)
                await page.wait_for_timeout(1500)
                html = await page.content()
            except:
                await page.close()
                return None

            await page.close()

            soup = BeautifulSoup(html, "html.parser")

            title = clean(soup.title.get_text() if soup.title else "")
            text = clean(soup.get_text())

            if not self.matches_filters(source, text):
                return None

            dates = extract_dates(text) + extract_textual_dates(text)

            published = None
            deadline = extract_deadline(text)

            if dates:
                if len(dates) > 1:
                    published = dates[0]
                    if not deadline:
                        deadline = dates[-1]
                elif not deadline:
                    deadline = dates[0]

            return {
                "title": title,
                "url": url,
                "summary": text[:300],
                "ente": source["name"],
                "published_at": published.strftime("%Y-%m-%d") if published else None,
                "deadline": deadline.strftime("%Y-%m-%d") if deadline else None,
                "source": source["name"],
                "hash": hashlib.sha1(url.encode()).hexdigest(),
            }

    # =========================
    # DEDUP
    # =========================
    def deduplicate(self, items):

        seen = {}

        for i in items:
            if i["hash"] not in seen:
                seen[i["hash"]] = i

        return list(seen.values())


# =========================
# ENTRY
# =========================
async def run_pipeline():
    return await Pipeline().run()
