# -*- coding: utf-8 -*-
# @File: parents.py
# @Author: yaccii
# @Time: 2025-11-17 18:06
# @Description:
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_profile_service
from app.domain import schemas
from app.services import ProfileService

router = APIRouter(prefix="/api/parents", tags=["parents"])


@router.post("/setup", response_model=schemas.ParentSetupResponse)
def setup_parent_child_device(
    req: schemas.ParentSetupRequest,
    db: Session = Depends(get_db),
    service: ProfileService = Depends(get_profile_service),
) -> schemas.ParentSetupResponse:
    """
    家长初始化绑定设备：
    - 创建/查找家长
    - 创建儿童
    - 绑定设备 + 玩具人设
    """
    try:
        return service.setup_parent_child_device(db, req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/children/{child_id}", response_model=schemas.ChildProfile)
def get_child_profile(
    child_id: int,
    db: Session = Depends(get_db),
    service: ProfileService = Depends(get_profile_service),
) -> schemas.ChildProfile:
    """
    查询儿童档案 + 设备信息。
    """
    try:
        return service.get_child_profile(db, child_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.patch("/children/{child_id}", response_model=schemas.ChildProfile)
def update_child_profile(
    child_id: int,
    req: schemas.ChildProfileUpdateRequest,
    db: Session = Depends(get_db),
    service: ProfileService = Depends(get_profile_service),
) -> schemas.ChildProfile:
    """
    更新儿童档案 / 玩具人设。
    """
    try:
        return service.update_child_profile(db, child_id, req)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
