from opensearchpy.exceptions import NotFoundError

from apps.api.app.models import SearchParams
from apps.api.app.search_service import SearchService


class MissingIndexClient:
    def search(self, *args, **kwargs):
        raise NotFoundError(404, "index_not_found_exception", "missing index")

    def get(self, *args, **kwargs):
        raise NotFoundError(404, "index_not_found_exception", "missing index")


def test_search_returns_empty_response_when_article_index_missing() -> None:
    service = SearchService(MissingIndexClient())
    response = service.search(SearchParams(q="gia vang"))

    assert response.total == 0
    assert response.results == []
    assert response.facets == {"category": [], "author": []}


def test_suggest_returns_empty_response_when_suggestion_index_missing() -> None:
    service = SearchService(MissingIndexClient())
    response = service.suggest("gia")

    assert response.suggestions == []
