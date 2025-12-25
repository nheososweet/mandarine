from typing import List, Optional
from pydantic import field_validator, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    
    All settings can be configured via .env file or environment variables.
    """
    
    # =============================================================================
    # APPLICATION
    # =============================================================================
    PROJECT_NAME: str = "Student Management API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    
    # =============================================================================
    # SERVER
    # =============================================================================
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # =============================================================================
    # POSTGRESQL DATABASE - Individual components
    # =============================================================================
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "123456"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "student_db"
    
    # Database URL - có thể set trực tiếp hoặc tự động build
    DATABASE_URL: Optional[str] = None
    
    # =============================================================================
    # DATABASE POOL SETTINGS
    # =============================================================================
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_ECHO_SQL: bool = False

    VECTOR_DB_PATH: str = "./chroma_db_store"

    API_V1_STR: str = "/api/v1"
    
    # =============================================================================
    # SECURITY
    # =============================================================================
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    LLM_BASE_URL: str = ""
    GEMINI_API_KEY: str = ""
    
    # =============================================================================
    # CORS
    # =============================================================================
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    
    # =============================================================================
    # LOGGING
    # =============================================================================
    LOG_LEVEL: str = "INFO"
    
    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def build_database_url(cls, v: Optional[str], info) -> str:
        """
        Build DATABASE_URL from components if not provided.
        
        Priority:
        1. Use DATABASE_URL if explicitly set in .env
        2. Build from POSTGRES_* components
        """
        if isinstance(v, str) and v:
            return v
        
        # Build from components
        user = info.data.get("POSTGRES_USER")
        password = info.data.get("POSTGRES_PASSWORD")
        host = info.data.get("POSTGRES_HOST")
        port = info.data.get("POSTGRES_PORT")
        db = info.data.get("POSTGRES_DB")
        
        return f"postgresql://{user}:{password}@{host}:{port}/{db}"
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v
    
    def get_database_url_sync(self) -> str:
        """Get synchronous database URL."""
        return self.DATABASE_URL
    
    def get_database_url_async(self) -> str:
        """Get asynchronous database URL (for future use)."""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow"  # Allow extra fields for future extensions
    )


# Create global settings instance
settings = Settings()


# Helper function to display current config (for debugging)
def print_config():
    """Print current configuration (hide sensitive data)."""
    print("=" * 80)
    print("📋 CURRENT CONFIGURATION")
    print("=" * 80)
    print(f"Project Name: {settings.PROJECT_NAME}")
    print(f"Version: {settings.APP_VERSION}")
    print(f"Debug Mode: {settings.DEBUG}")
    print(f"API Prefix: {settings.API_V1_PREFIX}")
    print("-" * 80)
    print(f"Database Host: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    print(f"Database Name: {settings.POSTGRES_DB}")
    print(f"Database User: {settings.POSTGRES_USER}")
    print(f"Database Password: {'*' * len(settings.POSTGRES_PASSWORD)}")
    print(f"Database URL: {settings.DATABASE_URL.replace(settings.POSTGRES_PASSWORD, '***')}")
    print("-" * 80)
    print(f"Pool Size: {settings.DB_POOL_SIZE}")
    print(f"Max Overflow: {settings.DB_MAX_OVERFLOW}")
    print(f"Echo SQL: {settings.DB_ECHO_SQL}")
    print("=" * 80)


if __name__ == "__main__":
    # Test config loading
    print_config()