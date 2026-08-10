"""
Pydantic Settings 配置管理。

所有配置通过环境变量 / .env 文件注入，支持多环境切换。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 所有嵌套子模型共享的 env_file 基础配置
_ENV_FILE = SettingsConfigDict(
    env_file=".env", env_file_encoding="utf-8", extra="ignore"
)


class MySQLSettings(BaseSettings):
    """MySQL 数据库配置。"""

    model_config = SettingsConfigDict(
        env_prefix="MYSQL_", **_ENV_FILE  # type: ignore[arg-type]
    )

    host: str = "127.0.0.1"
    port: int = 3306
    user: str = "root"
    password: str = "changeme"
    database: str = "med_device_agent"
    pool_size: int = 20
    pool_recycle: int = 3600

    @property
    def database_url(self) -> str:
        return (
            f"mysql+asyncmy://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"mysql+pymysql://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )


class RedisSettings(BaseSettings):
    """Redis 配置。"""

    model_config = SettingsConfigDict(env_prefix="REDIS_", **_ENV_FILE)  # type: ignore[arg-type]

    host: str = "127.0.0.1"
    port: int = 6379
    password: str = ""
    db: int = 0

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class QdrantSettings(BaseSettings):
    """Qdrant 向量数据库配置。"""

    model_config = SettingsConfigDict(env_prefix="QDRANT_", **_ENV_FILE)  # type: ignore[arg-type]

    host: str = "127.0.0.1"
    port: int = 6333
    api_key: str = ""


class DeepSeekSettings(BaseSettings):
    """DeepSeek LLM 配置。"""

    model_config = SettingsConfigDict(env_prefix="DEEPSEEK_", **_ENV_FILE)  # type: ignore[arg-type]

    api_key: str = ""
    base_url: str = "https://api.deepseek.com/v1"
    v3_model: str = "deepseek-chat"
    r1_model: str = "deepseek-reasoner"


class EmbeddingSettings(BaseSettings):
    """Embedding 模型配置。"""

    model_config = SettingsConfigDict(env_prefix="EMBEDDING_", **_ENV_FILE)  # type: ignore[arg-type]

    model: str = "BAAI/bge-small-zh-v1.5"
    dim: int = 512
    base_url: str = ""
    api_key: str = ""


class ASRSettings(BaseSettings):
    """FunASR + SenseVoice 配置。"""

    model_config = SettingsConfigDict(env_prefix="ASR_", **_ENV_FILE)  # type: ignore[arg-type]

    model_dir: str = "./models/sensevoice"
    model_name: str = "iic/SenseVoiceSmall"
    device: str = "cuda:0"


class TTSSettings(BaseSettings):
    """CosyVoice 2 配置。"""

    model_config = SettingsConfigDict(env_prefix="TTS_", **_ENV_FILE)  # type: ignore[arg-type]

    model_dir: str = "./models/cosyvoice2"
    model_name: str = "CosyVoice-300M-SFT"
    device: str = "cuda:0"


class JWTSettings(BaseSettings):
    """JWT 认证配置。"""

    model_config = SettingsConfigDict(env_prefix="JWT_", **_ENV_FILE)  # type: ignore[arg-type]

    secret_key: str = "change-me-to-a-random-secret"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 小时


class RateLimitSettings(BaseSettings):
    """限流配置。"""

    model_config = SettingsConfigDict(env_prefix="RATE_LIMIT_", **_ENV_FILE)  # type: ignore[arg-type]

    chat_per_minute: int = 20
    create_ticket_per_minute: int = 3
    transfer_human_per_minute: int = 2


class MinioSettings(BaseSettings):
    """MinIO 对象存储配置。"""

    model_config = SettingsConfigDict(env_prefix="MINIO_", **_ENV_FILE)  # type: ignore[arg-type]

    endpoint: str = "127.0.0.1:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    bucket: str = "smart-voice-agent"
    secure: bool = False


class CelerySettings(BaseSettings):
    """Celery 异步任务配置。"""

    model_config = SettingsConfigDict(env_prefix="CELERY_", **_ENV_FILE)  # type: ignore[arg-type]

    broker_url: str = "redis://127.0.0.1:6379/1"
    result_backend: str = "redis://127.0.0.1:6379/2"


class Settings(BaseSettings):
    """全局配置聚合。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = True
    app_name: str = "MedDeviceAgent"
    app_version: str = "0.1.0"

    # Server
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_workers: int = 4

    # Log
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    # Sub-settings
    mysql: MySQLSettings = MySQLSettings()
    redis: RedisSettings = RedisSettings()
    qdrant: QdrantSettings = QdrantSettings()
    deepseek: DeepSeekSettings = DeepSeekSettings()
    embedding: EmbeddingSettings = EmbeddingSettings()
    asr: ASRSettings = ASRSettings()
    tts: TTSSettings = TTSSettings()
    jwt: JWTSettings = JWTSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    minio: MinioSettings = MinioSettings()
    celery: CelerySettings = CelerySettings()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """获取配置单例（进程级缓存）。"""
    return Settings()