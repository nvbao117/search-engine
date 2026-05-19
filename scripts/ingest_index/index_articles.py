import argparse
import json
from pathlib import Path

from opensearchpy import OpenSearch, helpers

from apps.api.app.config import settings
from apps.api.app.text import fold_text
from apps.api.app.opensearch_client import get_client
from .common import read_jsonl, utc_now_iso

ARTICLE_INDEX_BODY = {
    "settings": {
        "analysis": {
            "filter": {
                "vi_synonyms": {
                    "type": "synonym_graph",
                    "synonyms": [
                        "tphcm, tp hcm, tp. hồ chí minh, thành phố hồ chí minh, sài gòn",
                        "hn, hà nội",
                        "bộ gdđt, bộ giáo dục và đào tạo",
                        "covid, covid-19, corona",
                    ],
                }
            },
            "analyzer": {
                "vi_news_analyzer": {
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding", "vi_synonyms"],
                }
            },
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {"type": "text", "analyzer": "vi_news_analyzer"},
            "summary": {"type": "text", "analyzer": "vi_news_analyzer"},
            "content": {"type": "text", "analyzer": "vi_news_analyzer"},
            "title_folded": {"type": "text"},
            "summary_folded": {"type": "text"},
            "content_folded": {"type": "text"},
            "author": {"type": "keyword"},
            "category": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "tags_text": {"type": "text", "analyzer": "vi_news_analyzer"},
            "tags_text_folded": {"type": "text"},
            "published_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "url": {"type": "keyword"},
            "status": {"type": "keyword"},
        }
    },
}

SUGGESTION_INDEX_BODY = {
    "mappings": {
        "properties": {
            "text": {"type": "text"},
            "text_folded": {"type": "text"},
            "type": {"type": "keyword"},
            "weight": {"type": "integer"},
        }
    }
}


def ensure_index(client: OpenSearch, name: str, body: dict, recreate: bool = False) -> None:
    if recreate and client.indices.exists(index=name):
        client.indices.delete(index=name)
    if not client.indices.exists(index=name):
        client.indices.create(index=name, body=body)


def swap_alias(client: OpenSearch, alias_name: str, index_name: str) -> None:
    actions: list[dict] = []
    if client.indices.exists_alias(name=alias_name):
        current = client.indices.get_alias(name=alias_name)
        actions.extend({"remove": {"index": existing, "alias": alias_name}} for existing in current)
    actions.append({"add": {"index": index_name, "alias": alias_name}})
    client.indices.update_aliases({"actions": actions})


def build_article_actions(index_name: str, records: list[dict]) -> list[dict]:
    return [
        {
            "_index": index_name,
            "_id": record["id"],
            "_source": record,
        }
        for record in records
    ]


def build_suggestion_actions(index_name: str, records: list[dict]) -> list[dict]:
    suggestions: dict[str, dict] = {}
    for record in records:
        title = record.get("title", "").strip()
        if title:
            suggestions.setdefault(
                title.casefold(),
                {
                    "text": title,
                    "text_folded": record.get("title_folded", ""),
                    "type": "title",
                    "weight": 100,
                },
            )
        for tag in record.get("tags", []):
            if not tag:
                continue
            suggestions.setdefault(
                tag.casefold(),
                {
                    "text": tag,
                    "text_folded": fold_text(tag),
                    "type": "tag",
                    "weight": 60,
                },
            )
    actions: list[dict] = []
    for index, suggestion in enumerate(suggestions.values(), start=1):
        actions.append({"_index": index_name, "_id": f"suggest_{index}", "_source": suggestion})
    return actions


def bulk_index(client: OpenSearch, actions: list[dict], batch_size: int) -> tuple[int, int]:
    success = 0
    failed = 0
    for ok, _ in helpers.streaming_bulk(client=client, actions=actions, chunk_size=batch_size, raise_on_error=False):
        if ok:
            success += 1
        else:
            failed += 1
    return success, failed


def index_articles(input_path: Path, recreate: bool, batch_size: int) -> dict:
    client = get_client()
    records = read_jsonl(input_path)
    ensure_index(client, settings.article_index_name, ARTICLE_INDEX_BODY, recreate=recreate)
    ensure_index(client, settings.suggestion_index_name, SUGGESTION_INDEX_BODY, recreate=recreate)
    success, failed = bulk_index(client, build_article_actions(settings.article_index_name, records), batch_size)
    suggest_success, suggest_failed = bulk_index(
        client,
        build_suggestion_actions(settings.suggestion_index_name, records),
        batch_size,
    )
    client.indices.refresh(index=settings.article_index_name)
    client.indices.refresh(index=settings.suggestion_index_name)
    swap_alias(client, settings.article_index_alias, settings.article_index_name)
    report = {
        "indexed": success,
        "failed": failed,
        "suggestions_indexed": suggest_success,
        "suggestions_failed": suggest_failed,
        "index": settings.article_index_name,
        "alias": settings.article_index_alias,
        "at": utc_now_iso(),
    }
    print(json.dumps(report, ensure_ascii=False))
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()
    index_articles(Path(args.input), recreate=args.recreate, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
