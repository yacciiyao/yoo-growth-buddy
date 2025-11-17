# -*- coding: utf-8 -*-
# @File: deps.py
# @Author: yaccii
# @Time: 2025-11-17 18:05
# @Description:
from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from app.infra.db import SessionLocal
from app.services import ProfileService


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


_profile_service = ProfileService()


def get_profile_service() -> ProfileService:
    return _profile_service
