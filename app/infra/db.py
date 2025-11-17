# -*- coding: utf-8 -*-
# @File: db.py
# @Author: yaccii
# @Time: 2025-11-17 16:53
# @Description:
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.infra.config import settings

# ORM 基类
Base = declarative_base()

# Engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
    echo=False,  # 调试
)

# Session 工厂
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI 依赖使用：yield 一个 Session，结束时自动关闭。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_session() -> Session:
    """
    脚本/工具使用：手动获取一个 Session。
    """
    return SessionLocal()
