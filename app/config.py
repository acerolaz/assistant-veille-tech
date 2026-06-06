from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = model_config["APP_ENV"]
    log_level: str = model_config["LOG_LEVEL"]

    azure_ai_inference_endpoint: str = model_config["AZURE_AI_INFERENCE_ENDPOINT"]
    azure_ai_inference_api_key: str = model_config["AZURE_AI_INFERENCE_API_KEY"]
    azure_ai_inference_model: str = model_config["AZURE_AI_INFERENCE_MODEL"]

    chroma_url: str = model_config["CHROMA_URL"]
    chroma_collection: str = model_config["CHROMA_COLLECTION"]
    embedding_model: str = model_config["EMBEDDING_MODEL"]

    news_api_key: str = model_config["NEWS_API_KEY"]
    news_api_base_url: str = model_config["NEWS_API_BASE_URL"]

    backend_port: int = model_config["BACKEND_PORT"]
    frontend_port: int = model_config["FRONTEND_PORT"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
