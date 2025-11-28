"""Application settings and configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_PREFIX: str = "/api"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "Trading Chatbot ADK Backend"
    BACKEND_CORS_ORIGINS: list[str] = ["*"]  # Chỉnh lại domain thật khi deploy

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # bỏ qua các biến môi trường không định nghĩa
    )


settings = Settings()
