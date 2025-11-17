# -*- coding: utf-8 -*-
# @File: voice_chat_service.py
# @Author: yaccii
# @Time: 2025-11-17 19:20
# @Description:
# -*- coding: utf-8 -*-
# @File: voice_chat_service.py
# @Author: yaccii
# @Time: 2025-11-17 19:20
# @Description:
from __future__ import annotations

import io
import logging
import os
import time
import wave
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infra import storage_s3
from app.infra.config import settings
from app.domain import models
from app.llm.model_selector import LlmModelSelector
from app.llm.registry import build_default_registry
from app.speech.asr_xfyun import AudioFormatError, SpeechError
from app.speech.client import SpeechClient

logger = logging.getLogger("yoo-growth-buddy.voice")


@dataclass
class VoiceTurnResult:
    """给 MQTT / 调用方用的结果对象"""

    child_id: int
    session_id: int
    turn_id: int
    user_text: str
    reply_text: str
    user_audio_path: str  # 相对路径（S3 key）
    reply_audio_path: str  # 相对路径（S3 key）
    reply_wav_bytes: bytes  # 回复语音的 WAV 字节


class VoiceChatService:
    """
    语音对话核心服务：
    - 输入：device_sn + wav_bytes（16k 单声道 16bit WAV）
    - 输出：本轮文本 + 语音回复 + DB 中的 session/turn 记录
    """

    def __init__(
        self,
        speech_client: Optional[SpeechClient] = None,
        llm_selector: Optional[LlmModelSelector] = None,
        file_base_path: Optional[str] = None,
        max_history_turns: int = 6,
    ) -> None:
        self._speech = speech_client or SpeechClient()
        registry = build_default_registry()
        self._llm_selector = llm_selector or LlmModelSelector(registry)
        self._base_path = file_base_path or getattr(settings, "FILE_BASE_PATH", "./data")
        self._max_history_turns = max_history_turns

    # ---------- 对外主入口：单轮对话 ----------

    async def handle_turn(
        self,
        db: Session,
        device_sn: str,
        wav_bytes: bytes,
        session_id: Optional[int] = None,
    ) -> VoiceTurnResult:
        """
        处理一轮语音对话。
        """
        # 1. 找到设备和孩子
        device, child = self._load_device_and_child(db, device_sn)

        # 2. session：如果没传就创建一个新的
        session = self._get_or_create_session(db, child, session_id)

        # 3. 本轮 seq
        seq = self._next_turn_seq(db, session.id)

        # 4. 保存孩子语音（S3）
        user_rel_path, _ = self._save_user_wav(child.id, session.id, seq, wav_bytes)

        # 5. ASR
        try:
            user_text_raw = await self._speech.asr(wav_bytes)
        except AudioFormatError as e:
            logger.error("ASR 音频格式错误: %s", e)
            raise
        except SpeechError as e:
            logger.error("ASR 识别失败: %s", e)
            raise

        user_text = (user_text_raw or "").strip()
        if not user_text:
            user_text = "（未识别到有效语音内容）"

        # 6. 构造 LLM messages
        messages = self._build_messages_for_llm(db, child, device, session, user_text)

        # 7. 调用 LLM
        provider, model_name, gen_cfg = self._llm_selector.select_for_child(child, task="chat")
        logger.info("调用 LLM: provider=%s, model=%s", getattr(provider, "name", "unknown"), model_name)

        reply_text_raw = await provider.chat(
            messages,
            model=model_name,
            max_tokens=int(gen_cfg.get("max_tokens", 256)),
            temperature=float(gen_cfg.get("temperature", 0.8)),
            extra_params={k: v for k, v in gen_cfg.items() if k not in ("max_tokens", "temperature")},
        )
        reply_text_raw = (reply_text_raw or "").strip()

        # 8. 安全收敛
        reply_text_final = self._sanitize_reply(child, reply_text_raw)

        # 9. TTS
        try:
            reply_pcm = await self._speech.tts(reply_text_final)
        except SpeechError as e:
            logger.error("TTS 合成失败: %s", e)
            raise

        # 10. PCM → WAV + 落盘（S3）
        reply_wav_bytes = _pcm_to_wav_bytes(reply_pcm)
        reply_rel_path, _ = self._save_reply_wav(child.id, session.id, seq, reply_wav_bytes)

        # 11. 写入 Turn（device_id 必须传）
        turn = models.Turn(
            session_id=session.id,
            device_id=device.id,
            seq=seq,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            created_at=int(time.time()),
        )
        db.add(turn)
        db.commit()
        db.refresh(turn)

        logger.info(
            "完成一轮对话: child_id=%s, session_id=%s, turn_id=%s, seq=%s",
            child.id,
            session.id,
            turn.id,
            seq,
        )

        return VoiceTurnResult(
            child_id=child.id,
            session_id=session.id,
            turn_id=turn.id,
            user_text=user_text,
            reply_text=reply_text_final,
            user_audio_path=user_rel_path,
            reply_audio_path=reply_rel_path,
            reply_wav_bytes=reply_wav_bytes,
        )

    def end_session(self, db: Session, session_id: int) -> models.ChatSession:
        """
        手动结束一个会话：自动生成 title
        """
        session = db.get(models.ChatSession, session_id)
        if session is None:
            raise ValueError(f"Session not found: id={session_id}")

        now_ts = int(time.time())

        if getattr(session, "ended_at", None) in (None, 0):
            session.ended_at = now_ts

        # 自动命名（只在原来没有标题时生成，避免覆盖手工命名）
        if not getattr(session, "title", None):
            session.title = self._generate_session_title(db, session)

        db.add(session)
        db.commit()
        db.refresh(session)
        logger.info("会话已结束并命名: session_id=%s, title=%s", session.id, session.title)
        return session

    # ---------- 内部辅助 ----------

    def _load_device_and_child(
        self,
        db: Session,
        device_sn: str,
    ) -> tuple[models.Device, models.Child]:
        device = (
            db.query(models.Device)
            .filter(models.Device.device_sn == device_sn)
            .first()
        )
        if device is None:
            raise ValueError(f"Device not found: sn={device_sn}")

        if device.bound_child_id is None:
            raise ValueError(f"Device not bound to child: sn={device_sn}")

        child = db.query(models.Child).get(device.bound_child_id)
        if child is None:
            raise ValueError(f"Child not found: id={device.bound_child_id}")

        return device, child

    def _get_or_create_session(
        self,
        db: Session,
        child: models.Child,
        session_id: Optional[int],
    ) -> models.ChatSession:
        if session_id is not None:
            session = db.get(models.ChatSession, session_id)
            if session is None or session.child_id != child.id:
                raise ValueError("Invalid session_id for this child")
            return session

        session = models.ChatSession()
        session.child_id = child.id
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def _next_turn_seq(self, db: Session, session_id: int) -> int:
        last_seq = (
            db.query(func.max(models.Turn.seq))
            .filter(models.Turn.session_id == session_id)
            .scalar()
        )
        if last_seq is None:
            return 1
        return int(last_seq) + 1

    def _build_messages_for_llm(
        self,
        db: Session,
        child: models.Child,
        device: models.Device,
        session: models.ChatSession,
        current_user_text: str,
    ) -> List[dict]:
        interests = _split_str(child.interests)
        forbidden = _split_str(child.forbidden_topics)

        toy_name = device.toy_name or "小悠"
        toy_persona = (
            device.toy_persona
            or f"一个叫{toy_name}的温柔可爱小伙伴，会认真听小朋友说话，轻声细语，喜欢鼓励和安慰小朋友。"
        )

        system_prompt = (
            f"你是一个儿童智能语音陪伴玩具，名字叫「{toy_name}」。"
            f"你的性格设定：{toy_persona}。"
            f"说话对象是一个大约 {child.age} 岁的孩子，性别：{child.gender or '未知'}。"
            f"孩子的兴趣：{', '.join(interests) if interests else '暂时未知'}。"
            f"家长禁止谈论的话题：{', '.join(forbidden) if forbidden else '无特别限制'}。"
            "和孩子聊天时要遵守这些原则："
            "1）用简短、温柔、具体的句子，像小朋友的好朋友一样说话；"
            "2）多鼓励、多肯定，避免批评；"
            "3）遇到危险、暴力、隐私、敏感内容时婉拒，并引导到安全健康的话题；"
            "4）不要出现成人世界的复杂概念（如色情、血腥、极端政治等）；"
            "5）一定用中文回答。"
        )

        messages: List[dict] = [
            {"role": "system", "content": system_prompt},
        ]

        history_turns: List[models.Turn] = (
            db.query(models.Turn)
            .filter(models.Turn.session_id == session.id)
            .order_by(models.Turn.seq.asc())
            .all()
        )

        if len(history_turns) > self._max_history_turns:
            history_turns = history_turns[-self._max_history_turns :]

        for t in history_turns:
            if t.user_text:
                messages.append({"role": "user", "content": t.user_text})
            if t.reply_text:
                messages.append({"role": "assistant", "content": t.reply_text})

        messages.append({"role": "user", "content": current_user_text})

        return messages

    def _sanitize_reply(self, child: models.Child, reply_text: str) -> str:
        text = reply_text or ""

        forbidden = _split_str(child.forbidden_topics)
        risk_keywords = set(forbidden) | {
            "自杀",
            "杀人",
            "暴力",
            "色情",
            "毒品",
            "赌博",
        }

        lowered = text.lower()

        def _contains_risk() -> bool:
            for kw in risk_keywords:
                if not kw:
                    continue
                if kw.lower() in lowered:
                    return True
            return False

        if not text or _contains_risk():
            toy_name = "小悠"
            return (
                f"{toy_name}觉得这个话题有点不安全，"
                "我们先不聊这个哦。"
                "要不要跟小悠说说你今天遇到的开心事情，"
                "或者聊聊你喜欢的玩具、动画片、游戏？"
            )

        return text

    def _generate_session_title(self, db: Session, session: models.ChatSession) -> str:
        first_turn: models.Turn | None = (
            db.query(models.Turn)
            .filter(models.Turn.session_id == session.id)
            .order_by(models.Turn.seq.asc())
            .first()
        )

        if first_turn is not None:
            base_text = first_turn.user_text or first_turn.reply_text or ""
            base_text = (base_text or "").replace("\n", " ").strip()
            if base_text:
                if len(base_text) > 20:
                    base_text = base_text[:20] + "..."
                return base_text

        ts = session.created_at or int(datetime.now().timestamp())
        dt = datetime.fromtimestamp(ts)
        date_str = dt.strftime("%Y-%m-%d")
        return f"{date_str} 和小yo的聊天"

    def _save_user_wav(
        self,
        child_id: int,
        session_id: int,
        seq: int,
        wav_bytes: bytes,
    ) -> tuple[str, str]:
        """保存孩子原始语音到 S3。"""
        key = f"children/{child_id}/sessions/{session_id}/turn_{seq}_user.wav"
        storage_s3.upload_bytes(key, wav_bytes, content_type="audio/wav")
        return key, key

    def _save_reply_wav(
        self,
        child_id: int,
        session_id: int,
        seq: int,
        reply_wav_bytes: bytes,
    ) -> tuple[str, str]:
        key = f"children/{child_id}/sessions/{session_id}/turn_{seq}_reply.wav"
        storage_s3.upload_bytes(key, reply_wav_bytes, content_type="audio/wav")
        return key, key

    # 本地保存版本，备选/调试
    def _save_user_wav_local(
        self,
        child_id: int,
        session_id: int,
        seq: int,
        wav_bytes: bytes,
    ) -> tuple[str, str]:
        rel_dir = os.path.join("children", str(child_id), "sessions", str(session_id))
        rel_path = os.path.join(rel_dir, f"turn_{seq}_user.wav")
        full_dir = os.path.join(self._base_path, rel_dir)
        os.makedirs(full_dir, exist_ok=True)
        full_path = os.path.join(self._base_path, rel_path)

        with open(full_path, "wb") as f:
            f.write(wav_bytes)

        return rel_path.replace("\\", "/"), full_path.replace("\\", "/")

    def _save_reply_wav_local(
        self,
        child_id: int,
        session_id: int,
        seq: int,
        reply_wav_bytes: bytes,
    ) -> tuple[str, str]:
        rel_dir = os.path.join("children", str(child_id), "sessions", str(session_id))
        rel_path = os.path.join(rel_dir, f"turn_{seq}_reply.wav")
        full_dir = os.path.join(self._base_path, rel_dir)
        os.makedirs(full_dir, exist_ok=True)
        full_path = os.path.join(self._base_path, rel_path)

        with open(full_path, "wb") as f:
            f.write(reply_wav_bytes)

        return rel_path.replace("\\", "/"), full_path.replace("\\", "/")


def _split_str(s: str | None) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def _pcm_to_wav_bytes(pcm: bytes, *, sample_rate: int = 16000) -> bytes:
    """
    把 16bit 单声道 PCM 包装成标准 WAV 字节。
    """
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()
