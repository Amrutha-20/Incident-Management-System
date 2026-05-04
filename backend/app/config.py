from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # PostgreSQL
    postgres_dsn: str = "postgresql://ims:ims_secret@postgres:5432/ims_db"

    # MongoDB
    mongo_uri: str = "mongodb://mongo:27017"
    mongo_db: str = "ims_signals"

    # Redis
    redis_url: str = "redis://redis:6379"

    # InfluxDB
    influx_url: str = "http://influxdb:8086"
    influx_token: str = "ims-influx-token"
    influx_org: str = "ims"
    influx_bucket: str = "ims_metrics"

    # Ring buffer
    ring_buffer_capacity: int = 50_000

    # Debounce window in seconds
    debounce_window_seconds: int = 10
    debounce_threshold: int = 100

    # Rate limiting
    rate_limit_per_minute: int = 6000  # 100/sec burst

    # Observability
    throughput_report_interval: int = 5

    # Worker concurrency
    worker_count: int = 4

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()