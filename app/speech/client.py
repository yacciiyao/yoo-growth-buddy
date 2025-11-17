# -*- coding: utf-8 -*-
# @File: client.py
# @Author: yaccii
# @Time: 2025-11-17 17:52
# @Description:
# app/speech/client.py
from __future__ import annotations

import asyncio
import ssl
from typing import Any, Dict

import certifi

from app.infra.config import settings
from app.speech.asr_xfyun import XfyunAsrClient
from app.speech.tts_xfyun import XfyunTtsClient


class SpeechClient:
    """
    语音服务统一入口：
    - asr(wav_bytes) -> 文本
    - tts(text) -> PCM 字节
    """

    def __init__(self) -> None:
        app_id = settings.XFYUN_APPID
        api_key = settings.XFYUN_APIKEY
        api_secret = settings.XFYUN_APISECRET

        if not (app_id and api_key and api_secret):
            raise ValueError("讯飞配置未完整设置，请检查 XFYUN_APPID/XFYUN_API_KEY/XFYUN_API_SECRET")

        if getattr(settings, "ENV", "dev") == "production":
            sslopt: Dict[str, Any] = {
                "cert_reqs": ssl.CERT_REQUIRED,
                "ca_certs": certifi.where(),
            }
        else:
            sslopt = {
                "cert_reqs": ssl.CERT_NONE,
            }

        self._asr = XfyunAsrClient(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret,
            sslopt=sslopt,
        )
        self._tts = XfyunTtsClient(
            app_id=app_id,
            api_key=api_key,
            api_secret=api_secret,
            sslopt=sslopt,
        )

    async def asr(self, wav_bytes: bytes) -> str:
        """
        语音识别。
        """
        return await asyncio.to_thread(self._asr.recognize, wav_bytes)

    async def tts(self, text: str) -> bytes:
        """
        文本转语音。
        """
        return await asyncio.to_thread(self._tts.synthesize, text)
