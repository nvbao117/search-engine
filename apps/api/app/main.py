from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import ClickEvent, FiltersResponse, SearchParams, SearchResponse, SuggestResponse
from .opensearch_client import get_client
from .search_service import SearchService

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_search_service() -> SearchService:
    return SearchService(get_client())


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/search", response_model=SearchResponse)
def search(params: SearchParams = Depends(), service: SearchService = Depends(get_search_service)) -> SearchResponse:
    return service.search(params)


@app.get("/suggest", response_model=SuggestResponse)
def suggest(q: str = "", service: SearchService = Depends(get_search_service)) -> SuggestResponse:
    return service.suggest(q=q)


@app.get("/articles/{article_id}")
def get_article(article_id: str, service: SearchService = Depends(get_search_service)) -> dict:
    return service.get_article(article_id)


@app.get("/filters", response_model=FiltersResponse)
def filters(service: SearchService = Depends(get_search_service)) -> FiltersResponse:
    return service.get_filters()


@app.post("/events/click", status_code=202)
def log_click(event: ClickEvent, service: SearchService = Depends(get_search_service)) -> dict[str, str]:
    service.log_click(event)
    return {"status": "accepted"}

