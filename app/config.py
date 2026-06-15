from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str
    log_level: str

    azure_ai_inference_endpoint: str
    azure_ai_inference_api_key: str
    azure_ai_inference_model: str

    chroma_url: str
    chroma_collection: str
    embedding_model: str

    news_api_key: str
    news_api_base_url: str

    db_url: str = ""

    websub_secret: str = ""
    websub_hub_url: str = "https://pubsubhubbub.appspot.com/"
    websub_callback_url: str = ""
    websub_lease_days: int = 1
    rss_feed_urls: list[str] = ["https://medium.com/feed/tag/csharp"]

    backend_port: int
    frontend_port: int

    @model_validator(mode="after")
    def _set_websub_callback_url(self) -> "Settings":
        if not self.websub_callback_url:
            self.websub_callback_url = (
                f"http://localhost:{self.backend_port}/webhook/websub"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
