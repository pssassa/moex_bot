from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://moex:moex@localhost:5432/moex"
    hf_token: str = ""
    hf_model: str = "Qwen/Qwen3.8-27B"
    hf_provider: str = "novita"
    forecast_cache_hours: int = 6
    candle_history_days: int = 500
    news_max_age_days: int = 14

    @field_validator("hf_token", "hf_model", "hf_provider", mode="before")
    @classmethod
    def strip_str(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


settings = Settings()
