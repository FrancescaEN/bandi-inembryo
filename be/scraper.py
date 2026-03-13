from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from sources import DEFAULT_KEYWORDS, DEFAULT_SCOPES, SOURCES


UTC = timezone.utc
TOPIC_CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_.-]{5,}$")


@dataclass(slots=True)
class ScrapeResult:
    source_id: str
    source_name: str
    source_kind: str
    publisher: str
    reliability: str
    title: str
    url: str
    summary: str
    published_at: str | None
    deadline_at: str | None
    matched_keywords: list[str]
    matched_scopes: list[str]
    score: int
    content_hash: str
    raw: dict[str, Any]


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split())


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    for parser_fn in (parsedate_to_datetime, date_parser.parse):
        try:
            parsed = parser_fn(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except Exception:
            continue

    return None


def _isoformat(value: datetime | None) -> str | None:
    return value.astimezone(UTC).isoformat() if value else None


class BandiPipeline:
    def __init__(
        self,
        *,
        keywords: list[str] | None = None,
        scopes: list[str] | None = None,
        days_back: int = 180,
        timeout: float = 20.0,
    ) -> None:
        self.keywords = keywords or DEFAULT_KEYWORDS
        self.scopes = scopes or DEFAULT_SCOPES
        self.days_back = days_back
        self.cutoff = datetime.now(tz=UTC) - timedelta(days=days_back)
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "BandiInEmbryoBot/1.0 "
                "(research pipeline for public tenders; contact: local-dev)"
            )
        }

    async def run(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(
            headers=self.headers,
            follow_redirects=True,
            timeout=self.timeout,
        ) as client:
            tasks = [
                self._fetch_source(client, source)
                for source in SOURCES
                if source.get("enabled", True)
            ]
            nested_results = await asyncio.gather(*tasks)

        collected = [item for batch in nested_results for item in batch]
        filtered = [item for item in collected if self._is_relevant(item)]
        deduplicated = self._deduplicate(filtered)
        deduplicated.sort(
            key=lambda item: (
                item["published_at"] is not None,
                item["published_at"] or "",
                item["score"],
            ),
            reverse=True,
        )
        return deduplicated

    async def _fetch_source(
        self,
        client: httpx.AsyncClient,
        source: dict[str, Any],
    ) -> list[dict[str, Any]]:
        try:
            response = await client.get(source["url"])
            response.raise_for_status()
        except Exception as exc:
            return [
                {
                    "source_id": source["id"],
                    "source_name": source["name"],
                    "source_kind": source["kind"],
                    "publisher": source.get("publisher", source["name"]),
                    "reliability": source.get("reliability", "unknown"),
                    "title": "",
                    "url": source["url"],
                    "summary": f"Errore recupero sorgente: {exc}",
                    "published_at": None,
                    "deadline_at": None,
                    "matched_keywords": [],
                    "matched_scopes": [],
                    "score": -1,
                    "content_hash": "",
                    "raw": {"error": str(exc)},
                    "status": "error",
                }
            ]

        if source["kind"] == "rss":
            return self._parse_rss(source, response.text)
        if source["kind"] == "html":
            return self._parse_html(source, response.text)
        if source["kind"] == "json":
            return self._parse_json(source, response.json())
        if source["kind"] == "topic_catalog":
            return self._parse_topic_catalog(source, response.text)
        return []

    def _parse_rss(self, source: dict[str, Any], payload: str) -> list[dict[str, Any]]:
        feed = feedparser.parse(payload)
        results = []
        for entry in feed.entries:
            published = _parse_datetime(
                entry.get("published")
                or entry.get("updated")
                or entry.get("created")
            )
            results.append(
                self._normalize(
                    source=source,
                    title=entry.get("title"),
                    url=entry.get("link"),
                    summary=entry.get("summary") or entry.get("description"),
                    published=published,
                    raw=dict(entry),
                )
            )
        return [item for item in results if item]

    def _parse_html(self, source: dict[str, Any], payload: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(payload, "html.parser")
        nodes = soup.select(source["list_selector"])
        results = []

        for node in nodes:
            title_node = node.select_one(source["title_selector"])
            link_node = node.select_one(source["link_selector"])
            summary_node = node.select_one(source.get("summary_selector", ""))
            date_node = node.select_one(source.get("date_selector", ""))

            title = _clean_text(title_node.get_text(" ", strip=True) if title_node else "")
            link = link_node.get("href", "").strip() if link_node else ""
            summary = _clean_text(summary_node.get_text(" ", strip=True) if summary_node else "")
            published = _parse_datetime(date_node.get_text(" ", strip=True) if date_node else "")

            if not title or not link:
                continue

            results.append(
                self._normalize(
                    source=source,
                    title=title,
                    url=urljoin(source["url"], link),
                    summary=summary,
                    published=published,
                    raw={"html": str(node)[:4000]},
                )
            )

        return [item for item in results if item]

    def _parse_json(self, source: dict[str, Any], payload: Any) -> list[dict[str, Any]]:
        items_path = source.get("items_path", [])
        items = payload
        for key in items_path:
            items = items.get(key, []) if isinstance(items, dict) else []

        results = []
        for entry in items if isinstance(items, list) else []:
            published = _parse_datetime(entry.get(source.get("published_field", "published_at")))
            results.append(
                self._normalize(
                    source=source,
                    title=entry.get(source.get("title_field", "title")),
                    url=entry.get(source.get("url_field", "url")),
                    summary=entry.get(source.get("summary_field", "summary")),
                    published=published,
                    raw=entry,
                )
            )

        return [item for item in results if item]

    def _parse_topic_catalog(
        self,
        source: dict[str, Any],
        payload: str,
    ) -> list[dict[str, Any]]:
        soup = BeautifulSoup(payload, "html.parser")
        results = []

        for link_node in soup.select("a[href]"):
            topic_code = _clean_text(link_node.get_text(" ", strip=True))
            if not TOPIC_CODE_PATTERN.match(topic_code):
                continue
            if not self._topic_allowed(source, topic_code):
                continue

            link = urljoin(source["url"], link_node.get("href", "").strip())
            summary = self._build_topic_summary(topic_code)
            results.append(
                self._normalize(
                    source=source,
                    title=topic_code,
                    url=link,
                    summary=summary,
                    published=None,
                    raw={
                        "topic_code": topic_code,
                        "programme": self._extract_programme(topic_code),
                    },
                )
            )

        return [item for item in results if item]

    def _normalize(
        self,
        *,
        source: dict[str, Any],
        title: str | None,
        url: str | None,
        summary: str | None,
        published: datetime | None,
        raw: dict[str, Any],
    ) -> dict[str, Any] | None:
        clean_title = _clean_text(title)
        clean_url = (url or "").strip()
        clean_summary = _clean_text(summary)

        if not clean_title or not clean_url:
            return None

        haystack = f"{clean_title} {clean_summary}".lower()
        matched_keywords = [term for term in self.keywords if term.lower() in haystack]
        matched_scopes = [term for term in self.scopes if term.lower() in haystack]
        score = len(matched_keywords) * 3 + len(matched_scopes)

        result = ScrapeResult(
            source_id=source["id"],
            source_name=source["name"],
            source_kind=source["kind"],
            publisher=source.get("publisher", source["name"]),
            reliability=source.get("reliability", "unknown"),
            title=clean_title,
            url=clean_url,
            summary=clean_summary,
            published_at=_isoformat(published),
            deadline_at=None,
            matched_keywords=matched_keywords,
            matched_scopes=matched_scopes,
            score=score,
            content_hash=hashlib.sha1(
                f"{clean_title}|{clean_url}".encode("utf-8")
            ).hexdigest(),
            raw=raw,
        )
        return asdict(result)

    def _is_relevant(self, item: dict[str, Any]) -> bool:
        if item.get("status") == "error":
            return False

        if not item["matched_keywords"]:
            return False

        published_at = _parse_datetime(item.get("published_at"))
        if published_at and published_at < self.cutoff:
            return False

        return True

    def _deduplicate(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}

        for item in items:
            key = item["content_hash"]
            current = by_key.get(key)
            if current is None or item["score"] > current["score"]:
                by_key[key] = item
                continue
            if item["score"] == current["score"]:
                current_published = current.get("published_at") or ""
                item_published = item.get("published_at") or ""
                if item_published > current_published:
                    by_key[key] = item

        return list(by_key.values())

    def _topic_allowed(self, source: dict[str, Any], topic_code: str) -> bool:
        prefixes = source.get("allowed_prefixes", [])
        if prefixes and not any(topic_code.startswith(prefix) for prefix in prefixes):
            return False

        years = source.get("allowed_years", [])
        if not years:
            return True

        return any(f"-{year}-" in topic_code or topic_code.endswith(f"-{year}") for year in years)

    def _extract_programme(self, topic_code: str) -> str:
        if topic_code.startswith("DIGITAL"):
            return "Digital Europe Programme"
        if topic_code.startswith("ERASMUS"):
            return "Erasmus+"
        if topic_code.startswith("HORIZON"):
            return "Horizon Europe"
        return "EU Funding & Tenders"

    def _build_topic_summary(self, topic_code: str) -> str:
        programme = self._extract_programme(topic_code)
        fragments = [fragment.lower() for fragment in re.split(r"[-_.]", topic_code) if fragment]
        mapped_terms = []

        if "digital" in fragments:
            mapped_terms.append("digital")
        if "skills" in fragments:
            mapped_terms.append("skills")
            mapped_terms.append("advanced digital skills")
        if "train" in fragments or "training" in fragments:
            mapped_terms.append("training")
        if "admin" in fragments or "administration" in fragments:
            mapped_terms.append("public administration")
            mapped_terms.append("innovazione amministrativa")
        if "gov" in fragments:
            mapped_terms.append("govtech")

        mapped_terms.append("capacity building")
        terms = " ".join(dict.fromkeys(mapped_terms))
        return f"{programme}. Topic code {topic_code}. {terms}".strip()


async def run_pipeline(
    *,
    days_back: int = 180,
    output_path: str | None = None,
) -> list[dict[str, Any]]:
    pipeline = BandiPipeline(days_back=days_back)
    results = await pipeline.run()

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2, ensure_ascii=False)

    return results
