from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def event_to_json(event: dict) -> dict:
    return {**event, "timestamp": event["timestamp"].isoformat()}


def parse_prometheus_metrics(payload: str) -> dict[str, float]:
    metrics = {}
    for line in payload.splitlines():
        if not line or line.startswith("#") or " " not in line:
            continue
        name, value = line.rsplit(" ", 1)
        metric_name = name.split("{", 1)[0]
        try:
            metrics[metric_name] = float(value)
        except ValueError:
            continue
    return metrics


class WebPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self.in_title = False
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.in_title = True
        if tag in {"script", "style", "noscript"}:
            self.ignored_depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style", "noscript"} and self.ignored_depth:
            self.ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        elif not self.ignored_depth:
            self.text_parts.append(data)


def scrape_web_page(url: str) -> dict:
    fetched_at = datetime.now(timezone.utc).isoformat()
    try:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Only HTTP and HTTPS URLs are supported")
        request = Request(url, headers={"User-Agent": "BootleggerIngestion/1.0"})
        with urlopen(request, timeout=5) as response:
            html = response.read(2_000_000).decode("utf-8", errors="replace")
            final_url = response.geturl()
        parser = WebPageParser()
        parser.feed(html)
        text = " ".join(" ".join(parser.text_parts).split())
        links = sorted({urljoin(final_url, link) for link in parser.links})
        return {
            "fetched_at": fetched_at,
            "url": final_url,
            "title": " ".join(" ".join(parser.title_parts).split()) or "Untitled page",
            "text": text,
            "word_count": len(text.split()),
            "link_count": len(links),
            "links": links[:100],
            "status": "healthy",
            "error": "",
        }
    except (OSError, URLError, UnicodeError, ValueError) as error:
        return {
            "fetched_at": fetched_at,
            "url": url,
            "title": "",
            "text": "",
            "word_count": 0,
            "link_count": 0,
            "links": [],
            "status": "error",
            "error": str(error),
        }
