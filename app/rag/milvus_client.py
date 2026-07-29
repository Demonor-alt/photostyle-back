"""Milvus 连接与通用字段配置。"""
from __future__ import annotations

import os

from pymilvus import connections
from app.utils.runtime import logger  # 日志记录器


_CONNECTION_ALIAS = os.getenv("MILVUS_ALIAS")


def get_connection_alias() -> str | None:
    """返回当前进程使用的 Milvus 连接别名。"""
    return _CONNECTION_ALIAS


def _get_milvus_token() -> str | None:
    """读取 Milvus token，本地无认证时返回 None。"""
    token = os.getenv("MILVUS_TOKEN")
    return token if token else None


def connect_milvus() -> None:
    """建立 Milvus 连接；重复调用时 pymilvus 会复用同一 alias。"""
    connections.connect(alias=_CONNECTION_ALIAS, uri=os.getenv("MILVUS_URI"), token=_get_milvus_token())
    logger.info("Milvus 连接成功")
