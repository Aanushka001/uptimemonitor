from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://vigil:vigil@localhost:5432/vigil"
    api_key: str = "change-me-api-key"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    worker_tick_seconds: int = 10
    worker_threads: int = 10

    allow_private_targets: bool = False
    enable_demo_endpoints: bool = False


settings = Settings()
