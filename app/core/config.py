from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Indian Market Intelligence Agent"
    app_version: str = "0.1.0"
    debug: bool = True

    database_url: str = "sqlite:///./data/market_agent.db"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()