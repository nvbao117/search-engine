from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError
from opensearchpy.exceptions import NotFoundError
from fastapi import HTTPException

from .config import settings
from .logging_utils import append_jsonl
from .models import ClickEvent, FiltersResponse, SearchParams, SearchResponse, SearchResult, SuggestItem, SuggestResponse
from .text import fold_text


class SearchService:
    def __init__(self, client: OpenSearch) -> None:
        self.client = client

    def search(self, params: SearchParams) -> SearchResponse:
        started_at = perf_counter()
        query = self._build_search_query(params)
        try:
            response = self.client.search(
                index=settings.article_index_alias,
                body=query,
            )
        except OpenSearchConnectionError as error:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            self._log_search_event(params, total=0, top_result_ids=[], latency_ms=elapsed_ms, index_ready=False)
            self._raise_backend_unavailable(error)
        except NotFoundError:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            self._log_search_event(params, total=0, top_result_ids=[], latency_ms=elapsed_ms, index_ready=False)
            return SearchResponse(
                query=params.q,
                total=0,
                page=params.page,
                page_size=params.page_size,
                latency_ms=elapsed_ms,
                results=[],
                facets={"category": [], "author": []},
            )
        elapsed_ms = int((perf_counter() - started_at) * 1000)

        hits = response.get("hits", {}).get("hits", [])
        total = response.get("hits", {}).get("total", {}).get("value", 0)
        facets = self._parse_facets(response.get("aggregations", {}))
        results = [self._to_search_result(hit) for hit in hits]

        self._log_search_event(
            params,
            total=total,
            top_result_ids=[item.id for item in results[:5]],
            latency_ms=elapsed_ms,
            index_ready=True,
        )

        return SearchResponse(
            query=params.q,
            total=total,
            page=params.page,
            page_size=params.page_size,
            latency_ms=elapsed_ms,
            results=results,
            facets=facets,
        )

    def suggest(self, q: str, limit: int | None = None) -> SuggestResponse:
        started_at = perf_counter()
        normalized = q.strip()
        folded = fold_text(normalized)
        body = {
            "size": limit or settings.suggest_limit,
            "_source": ["text", "type", "weight"],
            "query": {
                "bool": {
                    "should": [
                        {"match_phrase_prefix": {"text": {"query": normalized, "boost": 2}}},
                        {"match_phrase_prefix": {"text_folded": {"query": folded}}},
                    ],
                    "minimum_should_match": 1,
                }
            },
            "sort": [{"weight": "desc"}],
        }
        try:
            response = self.client.search(index=settings.suggestion_index_name, body=body)
        except OpenSearchConnectionError as error:
            self._raise_backend_unavailable(error)
        except NotFoundError:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            return SuggestResponse(query=normalized, latency_ms=elapsed_ms, suggestions=[])
        seen: set[str] = set()
        items: list[SuggestItem] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            text = source.get("text", "")
            key = text.casefold()
            if not text or key in seen:
                continue
            seen.add(key)
            items.append(
                SuggestItem(
                    text=text,
                    type=source.get("type", "title"),
                    weight=int(source.get("weight", 0)),
                )
            )
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        return SuggestResponse(query=normalized, latency_ms=elapsed_ms, suggestions=items)

    def get_article(self, article_id: str) -> dict[str, Any]:
        try:
            response = self.client.get(index=settings.article_index_alias, id=article_id)
        except OpenSearchConnectionError as error:
            self._raise_backend_unavailable(error)
        except NotFoundError as error:
            message = "Article index has not been created yet."
            if getattr(error, "error", "") != "index_not_found_exception":
                message = f"Article '{article_id}' was not found."
            raise HTTPException(status_code=404, detail=message) from error
        document = response.get("_source", {})
        return {
            "id": response.get("_id", article_id),
            **document,
        }

    def get_filters(self) -> FiltersResponse:
        body = {
            "size": 0,
            "aggs": {
                "category": {"terms": {"field": "category", "size": 20}},
                "author": {"terms": {"field": "author", "size": 20}},
            },
        }
        try:
            response = self.client.search(index=settings.article_index_alias, body=body)
        except OpenSearchConnectionError as error:
            self._raise_backend_unavailable(error)
        except NotFoundError:
            return FiltersResponse(category=[], author=[])
        facets = self._parse_facets(response.get("aggregations", {}))
        return FiltersResponse(
            category=facets["category"],
            author=facets["author"],
        )

    def log_click(self, event: ClickEvent) -> None:
        append_jsonl(
            settings.click_log_path,
            {
                "article_id": event.article_id,
                "query": event.query,
                "position": event.position,
                "clicked_at": (event.clicked_at or datetime.now(UTC)).isoformat(),
            },
        )

    def _build_search_query(self, params: SearchParams) -> dict[str, Any]:
        filters: list[dict[str, Any]] = []
        if params.category:
            filters.append({"term": {"category": params.category}})
        if params.author:
            filters.append({"term": {"author": params.author}})
        if params.from_date or params.to_date:
            range_query: dict[str, Any] = {}
            if params.from_date:
                range_query["gte"] = params.from_date.isoformat()
            if params.to_date:
                range_query["lte"] = params.to_date.isoformat()
            filters.append({"range": {"published_at": range_query}})

        sort = [{"published_at": {"order": "desc"}}]
        if params.q and params.sort.value == "relevance":
            sort = ["_score", {"published_at": {"order": "desc"}}]

        body: dict[str, Any] = {
            "from": (params.page - 1) * params.page_size,
            "size": params.page_size,
            "sort": sort,
            "aggs": {
                "category": {"terms": {"field": "category", "size": 10}},
                "author": {"terms": {"field": "author", "size": 10}},
            },
            "highlight": {
                "pre_tags": ["<em>"],
                "post_tags": ["</em>"],
                "fields": {
                    "title": {},
                    "summary": {},
                    "content": {"fragment_size": 180, "number_of_fragments": 1},
                },
            },
        }

        if not params.q:
            body["query"] = {
                "bool": {
                    "filter": filters,
                    "must": [{"term": {"status": "published"}}],
                }
            }
            return body

        folded = fold_text(params.q)
        body["query"] = {
            "bool": {
                "must": [
                    {
                        "bool": {
                            "should": [
                                {
                                    "multi_match": {
                                        "query": params.q,
                                        "fields": ["title^5", "tags_text^3", "summary^2", "content"],
                                        "type": "best_fields",
                                        "operator": "and",
                                    }
                                },
                                {
                                    "multi_match": {
                                        "query": folded,
                                        "fields": [
                                            "title_folded^5",
                                            "tags_text_folded^3",
                                            "summary_folded^2",
                                            "content_folded",
                                        ],
                                        "type": "best_fields",
                                        "operator": "and",
                                    }
                                },
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                    {"term": {"status": "published"}},
                ],
                "filter": filters,
            }
        }
        return body

    def _to_search_result(self, hit: dict[str, Any]) -> SearchResult:
        source = hit.get("_source", {})
        highlight = hit.get("highlight", {})
        return SearchResult(
            id=hit.get("_id", source.get("id", "")),
            title=source.get("title", ""),
            summary=source.get("summary", ""),
            url=source.get("url", ""),
            category=source.get("category", ""),
            author=source.get("author", ""),
            published_at=source.get("published_at"),
            highlight={
                "title": highlight.get("title", []),
                "summary": highlight.get("summary", []),
                "content": highlight.get("content", []),
            },
        )

    def _parse_facets(self, aggregations: dict[str, Any]) -> dict[str, list[dict[str, int | str]]]:
        return {
            "category": [
                {"value": bucket["key"], "count": bucket["doc_count"]}
                for bucket in aggregations.get("category", {}).get("buckets", [])
            ],
            "author": [
                {"value": bucket["key"], "count": bucket["doc_count"]}
                for bucket in aggregations.get("author", {}).get("buckets", [])
            ],
        }

    def _log_search_event(
        self,
        params: SearchParams,
        total: int,
        top_result_ids: list[str],
        latency_ms: int,
        index_ready: bool,
    ) -> None:
        append_jsonl(
            settings.search_log_path,
            {
                "query": params.q,
                "filters": {
                    "category": params.category,
                    "author": params.author,
                    "from_date": params.from_date.isoformat() if params.from_date else None,
                    "to_date": params.to_date.isoformat() if params.to_date else None,
                    "sort": params.sort.value,
                },
                "total": total,
                "top_result_ids": top_result_ids,
                "latency_ms": latency_ms,
                "zero_result": total == 0,
                "index_ready": index_ready,
            },
        )

    def _raise_backend_unavailable(self, error: OpenSearchConnectionError) -> None:
        raise HTTPException(
            status_code=503,
            detail="Search backend is unavailable. Make sure OpenSearch is running and reachable.",
        ) from error
