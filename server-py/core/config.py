"""
Application configuration via pydantic-settings.
Reads from .env in the project root and from environment variables.
"""

from functools import lru_cache
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="allow",
    )

    service_name: str = Field(default="coldcase")
    port: int = Field(
        default=7787,
        validation_alias=AliasChoices("BACKEND_PORT", "PORT"),
    )
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # Database
    mongodb_uri: str = Field(
        default="mongodb://localhost:27022",
        validation_alias=AliasChoices(
            "MONGODB_URI", "MONGO_URI", "LAUNCHPAD_MONGODB_CONNECTION_STRING"
        ),
    )
    database_name: str = Field(default="darwin_coldcase")

    # Auth
    is_dev_bypass_auth_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("IS_DEV_BYPASS_AUTH_ENABLED", "AUTH_BYPASS"),
    )

    # Storage
    enable_cloud_storage: bool = Field(default=False)
    upload_directory: str = Field(default="./uploads")

    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5178")

    # Providers (mock | real-option) — see docs/PATTERNS.md §1
    provider_employee: str = Field(default="mock")
    provider_email: str = Field(default="mock")
    provider_calendar: str = Field(default="mock")
    provider_training: str = Field(default="mock")
    provider_evaluation: str = Field(default="mock")
    provider_photos: str = Field(default="mock")


@lru_cache()
def get_settings() -> AppSettings:
    return AppSettings()
