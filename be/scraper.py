import asyncio
import hashlib
import re
from datetime import datetime

import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
from playwright.async_api import async_playwright

from sources import SOURCES


# =========================
# UTILS
# =========================
def clean(text):
    return " ".join(text.split()) if text else ""


def extract_dates(text):
    patterns = [
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{1,2}-\d{1,2}-\d{4}",
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


# =========================
# PIPELINE
# =========================
class Pipeline:

    def __init__(self):
        self.semaphore = asyncio.Semaphore(5)

    async def run(self):

        results = []

        for source in SOURCES:

            if not source["enabled"]:
                continue

            if source["mode"] == "rss":
                results += await self.fetch_rss(source)

            if source["mode"] == "playwright":
                results += await self.fetch_europa_innovazione(source)

        return self.deduplicate(results)

    # =========================
    # FILTRO INTELLIGENTE
    # =========================
    def matches_source_filters(self, source, text):

        text = text.lower()

        for group in source.get("required_keyword_groups", []):
            if not any(keyword in text for keyword in group):
                return False

        return True

    # =========================
    # RSS UE
    # =========================
    async def fetch_rss(self, source):

        print("Scraping EU Funding Portal (RSS)")

        feed = feedparser.parse(source["url"])

        results = []

        for entry in feed.entries:

            title = entry.title
            summary = getattr(entry, "summary", "")
            text = f"{title} {summary}".lower()

            if not self.matches_source_filters(source, text):
                continue

            try:
                published = datetime(*entry.published_parsed[:6])
            except:
                published = None

            results.append({
                "title": title,
                "url": entry.link,
                "summary": summary,
                "ente": "Commissione Europea",
                "published_at": published.strftime("%Y-%m-%d") if published else None,
                "deadline": None,
                "source": source["name"],
                "hash": hashlib.sha1(entry.link.encode()).hexdigest(),
            })

        return results

    # =========================
    # PLAYWRIGHT EUROPA INNOVAZIONE
    # =========================
    async def fetch_europa_innovazione(self, source):

        print("Scraping Europa Innovazione (Playwright)")

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

                if not href.startswith("https://www.europainnovazione.com"):
                    continue

                if "-" not in href:
                    continue

                if len(href) < 50:
                    continue

                links.append(href)

            links = list(set(links))[:30]

            print("LINK TROVATI:", len(links))

            # 🔥 PARALLELISMO
            tasks = [
                self.parse_detail_playwright(browser, source, url)
                for url in links
            ]

            pages = await asyncio.gather(*tasks)

            for p in pages:
                if p:
                    results.append(p)

            await browser.close()

        return results

    # =========================
    # DETTAGLIO PARALLELO
    # =========================
    async def parse_detail_playwright(self, browser, source, url):

        async with self.semaphore:

            page = await browser.new_page()

            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_timeout(1500)

                html = await page.content()

            except:
                await page.close()
                return None

            await page.close()

            soup = BeautifulSoup(html, "html.parser")

            title = clean(soup.title.get_text() if soup.title else "")
            text = clean(soup.get_text()).lower()

            # 🔥 FILTRO SERIO
            if not self.matches_source_filters(source, text):
                return None

            # ENTE
            if "horizon" in text:
                ente = "Horizon Europe"
            elif "erasmus" in text:
                ente = "Erasmus+"
            elif "digital europe" in text:
                ente = "Digital Europe Programme"
            elif "pnrr" in text:
                ente = "PNRR"
            else:
                ente = "Commissione Europea"

            # DATE
            dates = extract_dates(text)

            published = None
            deadline = None

            if dates:
                if len(dates) == 1:
                    deadline = dates[0]
                else:
                    published = dates[0]
                    deadline = dates[-1]

            return {
                "title": title,
                "url": url,
                "summary": text[:300],
                "ente": ente,
                "published_at": published.strftime("%Y-%m-%d") if published else None,
                "deadline": deadline.strftime("%Y-%m-%d") if deadline else None,
                "source": source["name"],
                "hash": hashlib.sha1(url.encode()).hexdigest(),
            }

    # =========================
    # DEDUPLICA
    # =========================
    def deduplicate(self, items):

        seen = {}

        for i in items:
            if i["hash"] not in seen:
                seen[i["hash"]] = i

        return list(seen.values())


# =========================
# ENTRY POINT
# =========================
async def run_pipeline():
    return await Pipeline().run()