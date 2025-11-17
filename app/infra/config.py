# -*- coding: utf-8 -*-
# @File: config.py
# @Author: yaccii
# @Time: 2025-11-17 16:52
# @Description:
from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    全局配置，从 .env / 环境变量读取。
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里多余变量直接忽略，不报错
    )

    # 运行环境
    ENV: str = Field("dev", description="运行环境: dev / prod")

    # 数据库
    DATABASE_URL: str = Field(
        ...,
        description="数据库连接串，例如 mysql+pymysql://user:pass@host:3306/dbname",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )

    # 文件根目录（音频等）
    FILE_ROOT: str = Field(
        "./data",
        description="音频等文件存储根目录",
        validation_alias=AliasChoices("FILE_ROOT", "file_base_path"),
    )

    # MQTT
    MQTT_BROKER_HOST: str = Field(
        "127.0.0.1",
        description="MQTT broker host",
        validation_alias=AliasChoices("MQTT_BROKER_HOST", "mqtt_host"),
    )
    MQTT_BROKER_PORT: int = Field(
        1883,
        description="MQTT broker port",
        validation_alias=AliasChoices("MQTT_BROKER_PORT", "mqtt_port"),
    )
    MQTT_USERNAME: Optional[str] = Field(
        None,
        description="MQTT 用户名（可选）",
        validation_alias=AliasChoices("MQTT_USERNAME", "mqtt_username"),
    )
    MQTT_PASSWORD: Optional[str] = Field(
        None,
        description="MQTT 密码（可选）",
        validation_alias=AliasChoices("MQTT_PASSWORD", "mqtt_password"),
    )

    # 讯飞语音（ASR/TTS）
    XFYUN_APPID: str = Field(
        ...,
        description="讯飞 APPID",
        validation_alias=AliasChoices("XFYUN_APPID", "xfyun_appid"),
    )
    XFYUN_APIKEY: str = Field(
        ...,
        description="讯飞 APIKey",
        validation_alias=AliasChoices("XFYUN_APIKEY", "xfyun_apikey"),
    )
    XFYUN_APISECRET: str = Field(
        ...,
        description="讯飞 APISecret",
        validation_alias=AliasChoices("XFYUN_APISECRET", "xfyun_apisecret"),
    )

    # 大模型默认 provider
    LLM_DEFAULT_PROVIDER: str = Field(
        "deepseek",
        description="默认大模型 provider: deepseek / openai / dummy 等",
        validation_alias=AliasChoices("LLM_DEFAULT_PROVIDER", "llm_default_provider"),
    )

    # DeepSeek
    DEEPSEEK_API_KEY: Optional[str] = Field(
        None,
        description="DeepSeek API key",
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "deepseek_api_key"),
    )
    DEEPSEEK_BASE_URL: Optional[str] = Field(
        None,
        description="DeepSeek API base url，例如 https://api.deepseek.com",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "deepseek_base_url"),
    )

    # OpenAI（预留）
    OPENAI_API_KEY: Optional[str] = Field(
        None,
        description="OpenAI API key",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    OPENAI_BASE_URL: Optional[str] = Field(
        None,
        description="OpenAI API base url（可选，自建代理时使用）",
        validation_alias=AliasChoices("OPENAI_BASE_URL", "openai_base_url"),
    )

    # 家长端简单鉴权（占位）
    ADMIN_TOKEN: Optional[str] = Field(
        None,
        description="家长管理端简单鉴权 token，占位，后续可换成真正用户系统",
        validation_alias=AliasChoices("ADMIN_TOKEN", "admin_token"),
    )

    # S3配置
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_S3_REGION: str
    AWS_S3_BUCKET: str
    AWS_S3_BASE_URL: str



settings = Settings()
