from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_name: str
    log_level: str
    database_url: str


def get_settings() -> Settings:
    load_dotenv(override=False)

    app_name = os.getenv("APP_NAME", "СтройМаркет — Операционный Дашборд").strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/stroymarket.db").strip()

    return Settings(
        app_name=app_name,
        log_level=log_level,
        database_url=database_url,
    )