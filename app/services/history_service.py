# -*- coding: utf-8 -*-
# @File: history_service.py
# @Author: yaccii
# @Time: 2025-11-17 20:50
# @Description:
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.domain import models, schemas
from app.infra import storage_s3


class HistoryService:
    """
    家长查看历史会话 / 轮次记录的查询服务。
    只读，不做任何写操作。
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    # -------- 会话列表（按 child） --------

    def list_sessions_for_child(self, child_id: int) -> List[schemas.SessionSummary]:
        """
        返回这个孩子的所有会话概要，按时间倒序。
        """
        child = self._db.query(models.Child).get(child_id)
        if child is None:
            return []

        sessions: List[models.ChatSession] = (
            self._db.query(models.ChatSession)
            .filter(models.ChatSession.child_id == child_id)
            .order_by(models.ChatSession.id.desc())
            .all()
        )

        result: List[schemas.SessionSummary] = []

        for s in sessions:
            turns: List[models.Turn] = (
                self._db.query(models.Turn)
                .filter(models.Turn.session_id == s.id)
                .order_by(models.Turn.seq.asc())
                .all()
            )

            if turns:
                started_at = getattr(s, "created_at", None) or turns[0].created_at
                ended_at: Optional[int] = (
                    getattr(s, "ended_at", None) or turns[-1].created_at
                )
                turn_count = len(turns)
                has_risk = any(getattr(t, "risk_flag", 0) == 1 for t in turns)
            else:
                started_at = getattr(s, "created_at", 0)
                ended_at = getattr(s, "ended_at", None)
                turn_count = 0
                has_risk = False

            summary = schemas.SessionSummary(
                session_id=s.id,
                title=getattr(s, "title", None),
                started_at=started_at,
                ended_at=ended_at,
                turn_count=turn_count,
                has_risk=has_risk,
            )
            result.append(summary)

        return result

    # -------- 单次会话详情 --------

    def get_session_detail(self, session_id: int) -> Optional[schemas.SessionDetail]:
        """
        返回某次会话的完整轮次（含文本 + 语音 URL + 风险标记）。
        """
        session = self._db.query(models.ChatSession).get(session_id)
        if session is None:
            return None

        child = self._db.query(models.Child).get(session.child_id)
        if child is None:
            return None

        device = (
            self._db.query(models.Device)
            .filter(models.Device.bound_child_id == child.id)
            .first()
        )
        device_sn = device.device_sn if device is not None else ""

        turns: List[models.Turn] = (
            self._db.query(models.Turn)
            .filter(models.Turn.session_id == session.id)
            .order_by(models.Turn.seq.asc())
            .all()
        )

        if turns:
            start_time = turns[0].created_at
            end_time = turns[-1].created_at
        else:
            start_time = getattr(session, "created_at", None)
            end_time = getattr(session, "ended_at", None)

        turns_payload: List[schemas.SessionTurn] = []
        for t in turns:
            user_audio_url = (
                storage_s3.build_url(t.user_audio_path)
                if t.user_audio_path
                else None
            )
            reply_audio_url = (
                storage_s3.build_url(t.reply_audio_path)
                if t.reply_audio_path
                else None
            )

            turns_payload.append(
                schemas.SessionTurn(
                    turn_id=t.id,
                    seq=t.seq,
                    created_at=t.created_at,
                    user_text=t.user_text or "",
                    reply_text=t.reply_text or "",
                    user_audio_url=user_audio_url,
                    reply_audio_url=reply_audio_url,
                    risk_flag=getattr(t, "risk_flag", 0),
                    risk_source=getattr(t, "risk_source", None),
                    risk_reason=getattr(t, "risk_reason", None),
                )
            )

        return schemas.SessionDetail(
            session_id=session.id,
            child_id=child.id,
            device_sn=device_sn,
            start_time=start_time,
            end_time=end_time,
            turns=turns_payload,
        )
