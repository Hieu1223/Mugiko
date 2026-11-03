"""Application configuration."""
import secrets
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    # Database
    database_url: str = "sqlite+aiosqlite:///../test/mugiko.db"
    database_echo: bool = True
    
    # Public base URL for built-in provider
    public_base_url: str = "http://localhost:8000"

    # Firebase
    firebase_project_id: str = ""
    firebase_credentials_path: str = ""
    
    # Admin token (for seeding)
    admin_token: str = ""
    
    # Security
    secret_key: str = secrets.token_urlsafe(32)
    
    # App
    app_env: str = "development"
    log_level: str = "INFO"
    
    # Logging
    log_dir: str = "log"
    log_file: str = "app.log"
    log_max_bytes: int = 10485760  # 10MB
    log_backup_count: int = 5
    # Structured logging
    db_log_file: str = "db.log"
    server_log_file: str = "server.log"
    traces_dir: str = "traces"
    trace_max_bytes: int = 1048576  # 1MB per trace file


settings = Settings()