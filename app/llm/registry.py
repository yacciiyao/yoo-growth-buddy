# -*- coding: utf-8 -*-
# @File: registry.py
# @Author: yaccii
# @Time: 2025-11-17 17:41
# @Description:
from __future__ import annotations

from typing import Dict, Tuple

from app.infra.config import settings
from app.llm.base import LlmProvider
from app.llm.deepseek_provider import DeepSeekProvider
from app.llm.dummy_provider import DummyProvider


class LlmProviderRegistry:
    """管理可用 Provider 的注册表。"""

    def __init__(self, providers: Dict[str, LlmProvider]) -> None:
        self._providers = providers

    def get(self, name: str) -> LlmProvider:
        try:
            return self._providers[name]
        except KeyError as e:
            raise KeyError(f"未注册的 LLM provider: {name}") from e

    def available_providers(self) -> Tuple[str, ...]:
        return tuple(self._providers.keys())


def build_default_registry() -> LlmProviderRegistry:
    """构建一份默认注册表"""
    providers: Dict[str, LlmProvider] = {}

    providers["dummy"] = DummyProvider()

    if settings.DEEPSEEK_API_KEY:
        try:
            providers["deepseek"] = DeepSeekProvider()
        except Exception:
            # DeepSeek 初始化失败时，仍然保留 dummy
            pass

    return LlmProviderRegistry(providers)
