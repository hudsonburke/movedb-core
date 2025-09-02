from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_ignore_empty=True,
        extra="ignore",
    )
    PROJECT_NAME: str = "MoveDB API"
    DATABASE_URL: str = "sqlite:///./test.db"
    VERSION: str = "0.4.0"
    CORS_ORIGINS: list[str] = ["*"]

settings = Settings() 
