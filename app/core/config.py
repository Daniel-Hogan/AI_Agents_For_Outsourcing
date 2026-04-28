from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    database_url: str = "postgresql+psycopg2://appuser:apppassword@localhost:5433/appdb"

    jwt_secret: str = "dev-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    frontend_origin: str = "http://localhost:5173"

    cookie_secure: bool = False
    cookie_samesite: str = "lax"  # lax|strict|none
    cookie_domain: str | None = None

    google_client_id: str | None = None
    google_client_secret: str | None = None

    resend_api_key: str | None = None
    email_from_address: str | None = None
    email_from_name: str = "AI Scheduler"
    app_base_url: str = "http://localhost:5173"

    log_level: str = "INFO"

    openrouteservice_api_key: str | None = None
    openrouteservice_base_url: str = "https://api.openrouteservice.org"
    openrouteservice_timeout_seconds: int = 10
    openrouteservice_profile: str = "driving-car"

    travel_warning_buffer_minutes: int = 10
    travel_warning_tight_window_minutes: int = 15

    organization_default_location: str | None = None
    organization_default_location_latitude: float | None = None
    organization_default_location_longitude: float | None = None

    @field_validator("organization_default_location_latitude", "organization_default_location_longitude", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value):
        if value == "":
            return None
        return value


settings = Settings()
