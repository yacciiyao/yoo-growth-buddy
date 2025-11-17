# -*- coding: utf-8 -*-
# @File: history.py
# @Author: yaccii
# @Time: 2025-11-17 20:51
# @Description:
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_db
from app.domain import schemas
from app.services.history_service import HistoryService

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get(
    "/children/{child_id}/sessions",
    response_model=List[schemas.SessionSummary],
)
def list_child_sessions(child_id: int, db=Depends(get_db)) -> List[schemas.SessionSummary]:
    """
    家长查看某个孩子的所有历史会话列表。
    """
    service = HistoryService(db)
    return service.list_sessions_for_child(child_id)


@router.get(
    "/sessions/{session_id}/turns",
    response_model=schemas.SessionDetail,
)
def get_session_turns(session_id: int, db=Depends(get_db)) -> schemas.SessionDetail:
    """
    查看某次会话的完整轮次（含文本、语音 URL、风险标记）。
    """
    service = HistoryService(db)
    data = service.get_session_detail(session_id)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: id={session_id}",
        )
    return data
