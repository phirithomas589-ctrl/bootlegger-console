from datetime import datetime, timezone
from unittest.mock import patch

from engine import event_to_json, parse_prometheus_metrics, scrape_web_page


class FakeResponse:
    def __init__(self, payload: bytes, url: str = "https://example.com/page") -> None:
        self.payload = payload
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, limit: int) -> bytes:
        assert limit == 2_000_000
        return self.payload

    def geturl(self) -> str:
        return self.url


def test_parse_prometheus_metrics_handles_comments_labels_and_invalid_values():
    payload = """# HELP node_load1 one minute load\nnode_load1 0.42\nhttp_requests_total{method=\"GET\"} 17\nbroken not-a-number\n"""

    assert parse_prometheus_metrics(payload) == {
        "node_load1": 0.42,
        "http_requests_total": 17.0,
    }


def test_scrape_web_page_extracts_text_and_resolves_links():
    html = b"""
    <html><head><title>Example page</title><style>.hidden { display: none; }</style></head>
    <body><h1>Welcome</h1><p>Readable content.</p><script>ignore this</script>
    <a href="/docs">Docs</a><a href="https://other.example/status">Status</a></body></html>
    """

    with patch("engine.urlopen", return_value=FakeResponse(html)):
        result = scrape_web_page("https://example.com/page")

    assert result["status"] == "healthy"
    assert result["title"] == "Example page"
    assert result["text"] == "Welcome Readable content. Docs Status"
    assert result["word_count"] == 5
    assert result["links"] == ["https://example.com/docs", "https://other.example/status"]


def test_scrape_web_page_rejects_non_http_urls_without_network_access():
    with patch("engine.urlopen") as mock_urlopen:
        result = scrape_web_page("file:///tmp/private.html")

    assert result["status"] == "error"
    assert "Only HTTP and HTTPS URLs are supported" in result["error"]
    mock_urlopen.assert_not_called()


def test_scrape_web_page_reports_fetch_failures():
    with patch("engine.urlopen", side_effect=OSError("connection refused")):
        result = scrape_web_page("https://example.com")

    assert result["status"] == "error"
    assert result["word_count"] == 0
    assert "connection refused" in result["error"]


def test_event_to_json_preserves_fields_and_serializes_timestamp():
    timestamp = datetime(2026, 9, 9, 12, 30, tzinfo=timezone.utc)
    event = {"id": "evt_1", "timestamp": timestamp, "records": 4}

    serialized = event_to_json(event)

    assert serialized["id"] == "evt_1"
    assert serialized["records"] == 4
    assert serialized["timestamp"] == "2026-09-09T12:30:00+00:00"
