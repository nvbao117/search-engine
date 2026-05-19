from datetime import datetime, time
from enum import Enum
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .text import normalize_unicode

VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")


class SortOption(str, Enum):
    relevance = "relevance"
    newest = "newest"


class ArticleDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    summary: str = ""
    content: str
    author: str = "Unknown"
    category: str = "Uncategorized"
    tags: list[str] = Field(default_factory=list)
    tags_text: str = ""
    title_folded: str = ""
    summary_folded: str = ""
    content_folded: str = ""
    tags_text_folded: str = ""
    published_at: datetime
    updated_at: datetime | None = None
    url: HttpUrl
    status: str = "published"

    @field_validator("title", "summary", "content", "author", "category", mode="before")
    @classmethod
    def normalize_text_fields(cls, value: str) -> str:
        return normalize_unicode(value or "")

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: list[str] | str | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [item.strip() for item in value.split(",") if item.strip()]
        return [normalize_unicode(item) for item in value if normalize_unicode(item)]


class SearchParams(BaseModel):
    q: str = ""
    category: str | None = None
    author: str | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    sort: SortOption = SortOption.relevance
    page: int = Field(default=1, ge=1, le=100)
    page_size: int = Field(default=10, ge=1, le=50)

    @field_validator("q", mode="before")
    @classmethod
    def normalize_query(cls, value: str | None) -> str:
        return normalize_unicode(value or "")

    @field_validator("q")
    @classmethod
    def validate_query_length(cls, value: str) -> str:
        if len(value) > 200:
            raise ValueError("q must be 200 characters or fewer")
        return value

    @field_validator("from_date", mode="before")
    @classmethod
    def normalize_from_date(cls, value: str | datetime | None) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=VN_TIMEZONE)
        if len(value) == 10:
            return datetime.combine(datetime.fromisoformat(value).date(), time.min, tzinfo=VN_TIMEZONE)
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=VN_TIMEZONE)

    @field_validator("to_date", mode="before")
    @classmethod
    def normalize_to_date(cls, value: str | datetime | None) -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=VN_TIMEZONE)
        if len(value) == 10:
            return datetime.combine(datetime.fromisoformat(value).date(), time.max, tzinfo=VN_TIMEZONE)
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=VN_TIMEZONE)


class HighlightBlock(BaseModel):
    title: list[str] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    content: list[str] = Field(default_factory=list)


class SearchResult(BaseModel):
    id: str
    title: str
    summary: str
    url: HttpUrl
    category: str
    author: str
    published_at: datetime
    highlight: HighlightBlock = Field(default_factory=HighlightBlock)


class SearchResponse(BaseModel):
    query: str
    total: int
    page: int
    page_size: int
    latency_ms: int
    results: list[SearchResult]
    facets: dict[str, list[dict[str, int | str]]]


class SuggestItem(BaseModel):
    text: str
    type: str
    weight: int


class SuggestResponse(BaseModel):
    query: str
    latency_ms: int
    suggestions: list[SuggestItem]


class FiltersResponse(BaseModel):
    category: list[dict[str, int | str]]
    author: list[dict[str, int | str]]


class ClickEvent(BaseModel):
    article_id: str
    query: str = ""
    position: int | None = None
    clicked_at: datetime | None = None
