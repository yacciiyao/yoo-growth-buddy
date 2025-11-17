# -*- coding: utf-8 -*-
# @File: base.py
# @Author: yaccii
# @Time: 2025-11-17 17:40
# @Description: 抽象基类 + ChatMessage 类型
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Mapping, Optional

ChatMessage = Mapping[str, str]


class LlmProvider(ABC):
    """统一的大模型调用接口。"""

    name: str

    @abstractmethod
    async def chat(
        self,
        messages: List[ChatMessage],
        model: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.8,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> str:
        raise NotImplementedError
