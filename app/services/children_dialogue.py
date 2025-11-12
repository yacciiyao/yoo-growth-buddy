# -*- coding: utf-8 -*-
# Author: yaccii.yao
# Date: 2025/2/25
# Description: 儿童多轮对话服务
import logging

from openai import OpenAI

from app.settings import settings

logger = logging.getLogger("smart-buddy")


class DeepSeekChildrenDialogue:
    def __init__(self,
                 model: str = "deepseek-reasoner",
                 max_history: int = 4,
                 temperature: float = 0.9,
                 max_tokens: int = 150
                 ):
        """
        儿童陪伴玩具专用对话服务
        :param model: 使用模型（默认deepseek-reasoner）
        :param max_history: 最大对话历史轮次（根据儿童注意力特点优化）
        :param temperature: 提高创造性（0.8-1.0）
        :param max_tokens: 限制回复长度
        """

        self.client = OpenAI(api_key=settings.DeepSeek_APIKey, base_url=settings.DeepSeek_BaseUrl)
        self.model = model
        self.max_history = max_history
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.messages = [
            {
                "role": "system",
                "content": """你是一个儿童智能陪伴玩具，遵循以下交互原则：
1. 使用简单易懂的短句子，适合6-12岁儿童理解
2. 语气温暖亲切，像大哥哥/大姐姐一样
3. 避免复杂抽象概念，用具体形象举例说明
4. 回复长度控制在3-5句话以内
5. 禁止使用任何表情符号或网络用语
6. 遇到无法回答的问题时引导到安全话题"""
            }
        ]

    def _truncate_history(self):
        """历史对话截断, 保留最近 N 轮对话"""
        if len(self.messages) > 2 + self.max_history * 2:  # 保留系统消息 + 最近对话
            self.messages = [self.messages[0]] + self.messages[-(self.max_history * 2):]

    def _safety_check(self, text: str):
        """内容安全性检查 TODO """
        forbidden_keywords = {"暴力", "死亡", "恐怖", "讨厌", "笨蛋"}
        return not any(keyword in text for keyword in forbidden_keywords)

    def chat(self, child_input: str) -> str:
        """
        执行儿童对话交互
        :param child_input: 儿童输入文本
        :return: 安全友好的回复内容
        """
        try:
            self.messages.append({"role": "user", "content": child_input})

            # 生成回复
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=self.messages,
            )

            raw_content = response.choices[0].message.content

            # 执行安全检查
            if not self._safety_check(raw_content):
                raise ValueError("监测到不适合儿童的内容")

            # 简化回复结构(删除推理过程)
            final_content = raw_content.replace("\n", " ").strip()

            # 保存对话历史
            self.messages.append({"role": "assistant", "content": final_content})
            self._truncate_history()

            return final_content

        except Exception as e:
            self.messages.pop()  # 移除问题
            logger.error(f"DeepSeekChildrenDialogue: {e}")
            return "哎呀，这个问题有点难呢！"
            pass
