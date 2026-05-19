from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Vietnamese News Search API"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    opensearch_url: str = "http://localhost:9200"
    opensearch_username: str = "admin"
    opensearch_password: str = "admin"
    article_index_alias: str = "news_articles_current"
    article_index_name: str = "news_articles_v1"
    suggestion_index_name: str = "news_suggestions_v1"
    request_timeout: int = 10
    search_log_path: Path = Path("logs/search.jsonl")
    click_log_path: Path = Path("logs/clicks.jsonl")
    default_page_size: int = 10
    max_page_size: int = 50
    max_page: int = 100
    max_query_length: int = 200
    suggest_limit: int = Field(default=8, le=20)
    cors_origins: list[str] = ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

