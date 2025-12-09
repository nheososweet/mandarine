from typing import Generator
from app.core.database import SessionLocal


def get_db() -> Generator:
    """
    Dependency để lấy database session.
    Tự động đóng session sau khi request hoàn thành.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()