from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


app_connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {
        "charset": "utf8mb4",
        "connect_timeout": 5,
        "read_timeout": 20,
        "write_timeout": 20,
    }
)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    connect_args=app_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

production_engine = (
    create_engine(
        settings.PRODUCTION_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=1800,
        pool_timeout=5,
        connect_args={
            "charset": "utf8mb4",
            "connect_timeout": 5,
            "read_timeout": 20,
            "write_timeout": 20,
        },
    )
    if settings.PRODUCTION_DATABASE_URL
    else None
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
