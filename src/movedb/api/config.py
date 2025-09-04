from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    PROJECT_NAME: str = "MoveDB API"
    DATABASE_URL: str = "sqlite:///./movedb.db"
    VERSION: str = "0.4.0"
    CORS_ORIGINS: list[str] = ["*"]

class TestSettings(Settings):
    model_config = SettingsConfigDict(
        env_file="../.test.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    DATABASE_URL: str = "sqlite:///./test.db"

settings = Settings()
test_settings = TestSettings()
