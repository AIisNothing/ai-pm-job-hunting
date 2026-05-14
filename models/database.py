"""SQLAlchemy 数据库引擎、会话与初始化配置"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DEFAULT_DB_PATH = os.path.join("data", "boss_zhipin.db")


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类"""
    pass


def _get_database_url(db_path: str | None = None) -> str:
    path = db_path or os.getenv("DATABASE_PATH", DEFAULT_DB_PATH)
    return f"sqlite:///{path}"


def get_engine(db_path: str | None = None):
    url = _get_database_url(db_path)
    return create_engine(url, echo=False)


# 默认引擎与会话工厂（应用启动时使用）
engine = get_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db(db_path: str | None = None) -> None:
    """创建所有数据表。如果指定 db_path 则使用该路径，否则使用默认路径。"""
    # 确保导入所有模型，以便 Base.metadata 包含全部表定义
    import models.tables  # noqa: F401

    target_engine = get_engine(db_path) if db_path else engine

    # 确保数据目录存在
    db_url = str(target_engine.url)
    if db_url.startswith("sqlite:///"):
        db_file = db_url.replace("sqlite:///", "")
        db_dir = os.path.dirname(db_file)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    Base.metadata.create_all(bind=target_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入：提供数据库会话，请求结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
