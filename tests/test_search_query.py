from apps.api.app.models import SearchParams
from apps.api.app.search_service import SearchService


class DummyClient:
    pass


def test_build_search_query_uses_folded_fields() -> None:
    service = SearchService(DummyClient())
    body = service._build_search_query(
        SearchParams(
            q="TPHCM",
            category="Thời sự",
            page=1,
            page_size=10,
        )
    )

    fields = body["query"]["bool"]["must"][0]["bool"]["should"][1]["multi_match"]["fields"]
    assert "title_folded^5" in fields
    assert body["query"]["bool"]["filter"] == [{"term": {"category": "Thời sự"}}]

