from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    BASE_DIR = BASE_DIR
    APP_NAME = "Sistema de Inventarios"
    DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
    PRODUCTION_DATABASE_URL = os.getenv(
        "PRODUCTION_DATABASE_URL",
        "",
    ).strip()
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", "8000"))
    INVENTORY_ADMIN_PASSWORD = os.getenv("INVENTORY_ADMIN_PASSWORD", "")


settings = Settings()

if not settings.DATABASE_URL.lower().startswith(("mysql://", "mysql+pymysql://")):
    raise RuntimeError(
        "DATABASE_URL debe estar definida en .env y apuntar a MySQL. "
        "Esta version de servidor no utiliza SQLite."
    )
