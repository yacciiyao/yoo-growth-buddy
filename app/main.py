# -*- coding: utf-8 -*-
# @File: main.py
# @Author: yaccii
# @Time: 2025-11-17 16:45
# @Description:
from __future__ import annotations

from fastapi import FastAPI

from app.api import parents as parents_api, history as history_api

app = FastAPI(
    title="yoo-growth-buddy",
    version="1.0.0",
)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}


# 家长相关接口
app.include_router(parents_api.router)
app.include_router(history_api.router)
