import os


class Settings:
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    database_url = os.getenv("DATABASE_URL", "postgresql://app:app@localhost:5432/app")
    smtp_host = os.getenv("SMTP_HOST", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025"))
    reports_dir = os.getenv("REPORTS_DIR", "/tmp/reports")
    cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "30"))


settings = Settings()
