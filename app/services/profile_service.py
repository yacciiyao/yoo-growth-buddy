# -*- coding: utf-8 -*-
# @File: profile_service.py
# @Author: yaccii
# @Time: 2025-11-17 17:55
# @Description:
from __future__ import annotations

from typing import List

from sqlalchemy.orm import Session

from app.domain import models, schemas


def _join_list(items: List[str]) -> str:
    """把字符串列表压成逗号分隔字符串存库。"""
    cleaned = [x.strip() for x in items if x and x.strip()]
    return ",".join(cleaned)


def _split_str(s: str | None) -> List[str]:
    """把逗号分隔字符串拆回列表，用于接口返回。"""
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


class ProfileService:
    """
    家长 / 儿童 / 设备配置相关：
    - 家长初始化绑定设备
    - 查询儿童档案
    - 更新儿童档案 / 玩具人设
    """

    def setup_parent_child_device(
        self,
        db: Session,
        req: schemas.ParentSetupRequest,
    ) -> schemas.ParentSetupResponse:
        """
        家长初始化绑定流程：
        - 如果不存在该邮箱的家长，则新建
        - 创建儿童信息
        - 创建或更新设备，并绑定到该儿童
        """
        # 1. 家长
        parent = (
            db.query(models.Parent)
            .filter(models.Parent.email == req.email)
            .first()
        )
        if parent is None:
            parent = models.Parent(
                email=req.email,
                password_hash=None,  # 目前不做登录
            )
            db.add(parent)
            db.flush()

        # 2. 儿童
        child = models.Child(
            parent_id=parent.id,
            name=req.child_name,
            age=req.child_age,
            gender=req.child_gender,
            interests=_join_list(req.child_interests),
            forbidden_topics=_join_list(req.child_forbidden_topics),
        )
        db.add(child)
        db.flush()

        # 3. 设备（按 device_sn 查，没有就建，有的话更新绑定和人设）
        device = (
            db.query(models.Device)
            .filter(models.Device.device_sn == req.device_sn)
            .first()
        )
        if device is None:
            device = models.Device(
                device_sn=req.device_sn,
                bound_child_id=child.id,
                toy_name=req.toy_name or "小悠",
                toy_age=req.toy_age or "8",
                toy_gender=req.toy_gender or "girl",
                toy_persona=(
                    req.toy_persona
                    or "一个叫小悠的温柔可爱小伙伴，会认真听小朋友说话，轻声细语，喜欢鼓励和安慰小朋友。"
                ),
            )
            db.add(device)
        else:
            device.bound_child_id = child.id
            if req.toy_name is not None:
                device.toy_name = req.toy_name
            if req.toy_age is not None:
                device.toy_age = req.toy_age
            if req.toy_gender is not None:
                device.toy_gender = req.toy_gender
            if req.toy_persona is not None:
                device.toy_persona = req.toy_persona

        db.commit()
        db.refresh(parent)
        db.refresh(child)
        db.refresh(device)

        return schemas.ParentSetupResponse(
            parent_id=parent.id,
            child_id=child.id,
            device_id=device.id,
        )

    def get_child_profile(
        self,
        db: Session,
        child_id: int,
    ) -> schemas.ChildProfile:
        """
        查询儿童档案 + 设备信息。
        """
        child = db.query(models.Child).get(child_id)
        if child is None:
            raise ValueError(f"Child not found: id={child_id}")

        parent = child.parent
        if parent is None:
            raise ValueError(f"Parent not found for child: id={child_id}")

        device = (
            db.query(models.Device)
            .filter(models.Device.bound_child_id == child.id)
            .first()
        )
        if device is None:
            raise ValueError(f"Device not found for child: id={child_id}")

        return schemas.ChildProfile(
            parent_id=parent.id,
            parent_email=parent.email,
            child_id=child.id,
            child_name=child.name,
            child_age=child.age,
            child_gender=child.gender or "",
            child_interests=_split_str(child.interests),
            child_forbidden_topics=_split_str(child.forbidden_topics),
            device_id=device.id,
            device_sn=device.device_sn,
            toy_name=device.toy_name or "小悠",
            toy_age=device.toy_age,
            toy_gender=device.toy_gender,
            toy_persona=device.toy_persona,
        )

    def update_child_profile(
        self,
        db: Session,
        child_id: int,
        req: schemas.ChildProfileUpdateRequest,
    ) -> schemas.ChildProfile:
        """
        更新儿童档案 + 玩具人设。
        """
        child = db.query(models.Child).get(child_id)
        if child is None:
            raise ValueError(f"Child not found: id={child_id}")

        parent = child.parent
        if parent is None:
            raise ValueError(f"Parent not found for child: id={child_id}")

        device = (
            db.query(models.Device)
            .filter(models.Device.bound_child_id == child.id)
            .first()
        )

        # 更新儿童信息
        if req.child_name is not None:
            child.name = req.child_name
        if req.child_age is not None:
            child.age = req.child_age
        if req.child_gender is not None:
            child.gender = req.child_gender
        if req.child_interests is not None:
            child.interests = _join_list(req.child_interests)
        if req.child_forbidden_topics is not None:
            child.forbidden_topics = _join_list(req.child_forbidden_topics)

        # 更新玩具人设
        if device is not None:
            if req.toy_name is not None:
                device.toy_name = req.toy_name
            if req.toy_age is not None:
                device.toy_age = req.toy_age
            if req.toy_gender is not None:
                device.toy_gender = req.toy_gender
            if req.toy_persona is not None:
                device.toy_persona = req.toy_persona

        db.commit()
        db.refresh(child)
        if device is not None:
            db.refresh(device)

        # 重新加载最新设备
        if device is None:
            return schemas.ChildProfile(
                parent_id=parent.id,
                parent_email=parent.email,
                child_id=child.id,
                child_name=child.name,
                child_age=child.age,
                child_gender=child.gender or "",
                child_interests=_split_str(child.interests),
                child_forbidden_topics=_split_str(child.forbidden_topics),
                device_id=0,
                device_sn="",
                toy_name="小悠",
                toy_age=None,
                toy_gender=None,
                toy_persona=None,
            )

        return schemas.ChildProfile(
            parent_id=parent.id,
            parent_email=parent.email,
            child_id=child.id,
            child_name=child.name,
            child_age=child.age,
            child_gender=child.gender or "",
            child_interests=_split_str(child.interests),
            child_forbidden_topics=_split_str(child.forbidden_topics),
            device_id=device.id,
            device_sn=device.device_sn,
            toy_name=device.toy_name or "小悠",
            toy_age=device.toy_age,
            toy_gender=device.toy_gender,
            toy_persona=device.toy_persona,
        )
