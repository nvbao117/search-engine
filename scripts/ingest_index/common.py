import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from dateutil import parser
from zoneinfo import ZoneInfo

from apps.api.app.text import fold_text, normalize_unicode

TRACKING_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref")
VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")
REQUIRED_FIELDS = ("id", "title", "content", "published_at", "url", "status")


def normalize_url(raw_url: str) -> str:
    parsed = urlparse(normalize_unicode(raw_url))
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=False)
        if not any(key.lower().startswith(prefix) for prefix in TRACKING_PREFIXES)
    ]
    clean = parsed._replace(query=urlencode(query), fragment="")
    return urlunparse(clean)


def normalize_datetime(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    parsed = parser.parse(raw_value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TIMEZONE)
    localized = parsed.astimezone(VN_TIMEZONE)
    return localized.isoformat()


def article_signature(title: str, content: str) -> str:
    payload = f"{normalize_unicode(title)}::{normalize_unicode(content)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def transform_record(record: dict) -> dict | None:
    title = normalize_unicode(record.get("title", ""))
    content = normalize_unicode(record.get("content", ""))
    published_at = normalize_datetime(record.get("published_at"))
    url = normalize_url(record.get("url", ""))
    normalized = {
        "id": normalize_unicode(str(record.get("id", ""))),
        "title": title,
        "summary": normalize_unicode(record.get("summary", "")),
        "content": content,
        "author": normalize_unicode(record.get("author", "") or "Unknown"),
        "category": normalize_unicode(record.get("category", "") or "Uncategorized"),
        "tags": [normalize_unicode(tag) for tag in record.get("tags", []) if normalize_unicode(tag)],
        "published_at": published_at,
        "updated_at": normalize_datetime(record.get("updated_at")) or published_at,
        "url": url,
        "status": normalize_unicode(record.get("status", "") or "published").lower(),
    }

    if any(not normalized.get(field) for field in REQUIRED_FIELDS):
        return None

    normalized["tags_text"] = " ".join(normalized["tags"])
    normalized["title_folded"] = fold_text(normalized["title"])
    normalized["summary_folded"] = fold_text(normalized["summary"])
    normalized["content_folded"] = fold_text(normalized["content"])
    normalized["tags_text_folded"] = fold_text(normalized["tags_text"])
    normalized["dedupe_hash"] = article_signature(title, content)
    return normalized


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()

