# -*- coding: utf-8 -*-
# @File: models.py
# @Author: yaccii
# @Time: 2025-11-17 16:57
# @Description:
from __future__ import annotations

import time
from typing import List, Optional

from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from app.infra.db import Base


class Parent(Base):
    __tablename__ = "parents"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = Column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = Column(String(255), nullable=True)

    created_at: Mapped[int] = Column(
        BigInteger,
        nullable=False,
        default=int(time.time()),
    )
    updated_at: Mapped[Optional[int]] = Column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=int(time.time()),
    )

    # 关系
    children: Mapped[List["Child"]] = relationship(
        "Child",
        back_populates="parent",
        cascade="all, delete-orphan",
    )


class Child(Base):
    __tablename__ = "children"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int] = Column(
        Integer,
        ForeignKey("parents.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = Column(String(50), nullable=False)
    age: Mapped[int] = Column(Integer, nullable=False)
    gender: Mapped[Optional[str]] = Column(String(20), nullable=True)  # boy/girl/other

    interests: Mapped[Optional[str]] = Column(
        String(512),
        nullable=True,
        doc="兴趣列表，逗号分隔存储",
    )
    forbidden_topics: Mapped[Optional[str]] = Column(
        String(512),
        nullable=True,
        doc="禁止话题列表，逗号分隔存储",
    )

    created_at: Mapped[int] = Column(
        BigInteger,
        nullable=False,
        default=int(time.time()),
    )
    updated_at: Mapped[Optional[int]] = Column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=int(time.time()),
    )

    # 关系
    parent: Mapped["Parent"] = relationship("Parent", back_populates="children")
    sessions: Mapped[List["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="child",
        cascade="all, delete-orphan",
    )

    # 1:1 绑定设备（通过 Device.bound_child_id）
    device: Mapped[Optional["Device"]] = relationship(
        "Device",
        uselist=False,
        primaryjoin="Child.id==Device.bound_child_id",
        viewonly=True,
    )


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    device_sn: Mapped[str] = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    bound_child_id: Mapped[Optional[int]] = Column(
        Integer,
        ForeignKey("children.id"),
        nullable=True,
        index=True,
    )

    toy_name: Mapped[Optional[str]] = Column(String(50), nullable=True)
    toy_age: Mapped[Optional[str]] = Column(String(10), nullable=True)
    toy_gender: Mapped[Optional[str]] = Column(String(20), nullable=True)
    toy_persona: Mapped[Optional[str]] = Column(Text, nullable=True)

    created_at: Mapped[int] = Column(
        BigInteger,
        nullable=False,
        default=int(time.time()),
    )
    updated_at: Mapped[Optional[int]] = Column(
        BigInteger,
        nullable=True,
        default=None,
        onupdate=int(time.time()),
    )
    last_seen_at: Mapped[Optional[int]] = Column(
        BigInteger,
        nullable=True,
        default=None,
    )

    # 关系
    child: Mapped[Optional["Child"]] = relationship(
        "Child",
        primaryjoin="Device.bound_child_id==Child.id",
        viewonly=True,
    )
    turns: Mapped[List["Turn"]] = relationship(
        "Turn",
        back_populates="device",
    )


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    child_id: Mapped[int] = Column(
        Integer,
        ForeignKey("children.id"),
        nullable=False,
        index=True,
    )

    title: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        doc="会话标题，可自动生成",
    )

    # 会话开始/结束时间
    started_at: Mapped[int] = Column(
        BigInteger,
        nullable=False,
        default=int(time.time()),
    )
    ended_at: Mapped[Optional[int]] = Column(
        BigInteger,
        nullable=True,
        default=None,
    )

    # 关系
    child: Mapped["Child"] = relationship("Child", back_populates="sessions")
    turns: Mapped[List["Turn"]] = relationship(
        "Turn",
        back_populates="session",
        order_by="Turn.seq",
        cascade="all, delete-orphan",
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = Column(
        Integer,
        ForeignKey("chat_sessions.id"),
        nullable=False,
        index=True,
    )
    device_id: Mapped[int] = Column(
        Integer,
        ForeignKey("devices.id"),
        nullable=False,
        index=True,
    )

    # 会话内顺序
    seq: Mapped[int] = Column(Integer, nullable=False)

    user_text: Mapped[Optional[str]] = Column(Text, nullable=True)
    reply_text: Mapped[Optional[str]] = Column(Text, nullable=True)

    # 存储相对 FILE_ROOT 的路径，如 audio/child_1/s1_t1_user.wav
    user_audio_path: Mapped[Optional[str]] = Column(String(512), nullable=True)
    reply_audio_path: Mapped[Optional[str]] = Column(String(512), nullable=True)

    # 消息创建时间
    created_at: Mapped[int] = Column(
        BigInteger,
        nullable=False,
        default=int(time.time()),
    )

    # 风险标记：主要针对儿童输入（家长用来监控孩子行为）
    risk_flag: Mapped[bool] = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="是否存在安全风险（通常指儿童输入触发安全规则）",
    )
    risk_source: Mapped[Optional[str]] = Column(
        String(20),
        nullable=True,
        doc="风险来源：input / output / both",
    )
    risk_reason: Mapped[Optional[str]] = Column(
        String(255),
        nullable=True,
        doc="风险原因简要说明，用于家长端提示和日志",
    )

    # 关系
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="turns")
    device: Mapped["Device"] = relationship("Device", back_populates="turns")
