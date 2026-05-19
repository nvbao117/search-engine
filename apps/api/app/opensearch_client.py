from functools import lru_cache

from opensearchpy import OpenSearch

from .config import settings


@lru_cache(maxsize=1)
def get_client() -> OpenSearch:
    auth = None
    if settings.opensearch_username:
        auth = (settings.opensearch_username, settings.opensearch_password)
    return OpenSearch(
        hosts=[settings.opensearch_url],
        http_auth=auth,
        use_ssl=settings.opensearch_url.startswith("https://"),
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
        timeout=settings.request_timeout,
    )
