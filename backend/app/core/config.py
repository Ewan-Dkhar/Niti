"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Values come from environment variables or a local ``.env`` file.
    ``.env.example`` documents every supported key.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    data_dir: str = "data"

    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    sarvam_api_key: str | None = None

    extraction_provider: str = "auto"
    extraction_model: str | None = None
    simplification_model: str = "openai/gpt-oss-120b"

    sarvam_tts_model: str = "bulbul:v3"
    sarvam_speaker: str = "shreya"

    myscheme_api_url: str = "https://www.myscheme.gov.in/api/apisetu/schemes"
    pib_rss_url: str = "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3"

    qdrant_url: str | None = None
    qdrant_api_key: str | None = None
    qdrant_path: str = "data/qdrant"
    qdrant_collection: str = "niti_chunks"

    dense_embedding_model: str = "intfloat/multilingual-e5-large"
    sparse_embedding_model: str = "Qdrant/bm25"

    use_mock_llm: bool = True
    use_mock_tts: bool = True
    use_docling: bool = False
    offline_mode: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
