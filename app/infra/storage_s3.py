# -*- coding: utf-8 -*-
# @File: storage_s3.py
# @Author: yaccii
# @Time: 2025-11-17 20:33
# @Description:
from __future__ import annotations

import boto3
from botocore.client import Config

from app.infra.config import settings
from app.infra.ylogger import ylogger

_session = boto3.session.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_S3_REGION,
)

_s3 = _session.client("s3", config=Config(s3={"addressing_style": "virtual"}))


def upload_bytes(key: str, data: bytes, content_type: str = "audio/wav") -> None:
    ylogger.info("Upload to S3: bucket=%s, key=%s, size=%s", settings.AWS_S3_BUCKET, key, len(data))
    _s3.put_object(
        Bucket=settings.AWS_S3_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def build_url(key: str) -> str:
    base = settings.AWS_S3_BASE_URL.rstrip("/")
    return f"{base}/{key.lstrip('/')}"
