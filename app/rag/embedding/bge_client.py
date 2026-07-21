"""BGE 中文向量模型客户端。"""
from __future__ import annotations

import os
from functools import lru_cache

from app.utils.runtime import logger

# 默认使用 bge-base-zh-v1.5，可通过 EMBEDDING_MODEL_NAME 指向 HuggingFace 模型名或本地模型目录。
_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-base-zh-v1.5")
# 允许通过环境变量指定运行设备，例如 cpu、cuda、cuda:0；不指定时由 sentence-transformers 自动判断。
_DEVICE = os.getenv("EMBEDDING_DEVICE") or None
# BGE 系列推荐查询侧加检索指令，文档侧不加；可通过环境变量覆盖或置空。
_QUERY_PREFIX = os.getenv("BGE_QUERY_PREFIX", "为这个句子生成表示以用于检索相关文章：")


@lru_cache(maxsize=1)
def _get_model():
    """懒加载并缓存 SentenceTransformer 模型，避免每次向量化都重复加载。"""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("缺少 sentence-transformers 依赖，请先安装 requirements.txt 中的依赖") from exc

    kwargs = {"device": _DEVICE} if _DEVICE else {}
    logger.info("embedding.model.loading name=%s device=%s", _MODEL_NAME, _DEVICE or "auto")
    model = SentenceTransformer(_MODEL_NAME, **kwargs)
    logger.info("embedding.model.loaded name=%s dimension=%s", _MODEL_NAME, model.get_sentence_embedding_dimension())
    return model


def get_embedding_model_name() -> str:
    """返回当前使用的 embedding 模型名称，便于写入 metadata 和排查问题。"""
    return _MODEL_NAME


def get_embedding_dimension() -> int:
    """返回当前模型输出向量维度，用于创建或校验 Milvus collection。"""
    return int(_get_model().get_sentence_embedding_dimension())


def embed_text(text: str, *, for_query: bool = False) -> list[float]:
    """将单条文本转换为归一化向量。"""
    text = text.strip()
    if not text:
        raise ValueError("embedding text cannot be empty")

    # 查询向量使用 BGE 查询前缀，入库文档向量保持原文，减少语义偏移。
    embedding_text = f"{_QUERY_PREFIX}{text}" if for_query and _QUERY_PREFIX else text
    vector = _get_model().encode(
        embedding_text,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    # Milvus FLOAT_VECTOR 使用 float32 即可，转 list 便于 pymilvus 序列化。
    return vector.astype("float32").tolist()


def embed_texts(texts: list[str], *, for_query: bool = False) -> list[list[float]]:
    """批量将文本转换为归一化向量。"""
    cleaned = [text.strip() for text in texts]
    if any(not text for text in cleaned):
        raise ValueError("embedding texts cannot contain empty text")

    # 批量查询向量同样添加查询前缀；批量文档入库则不添加。
    embedding_texts = [f"{_QUERY_PREFIX}{text}" for text in cleaned] if for_query and _QUERY_PREFIX else cleaned
    vectors = _get_model().encode(
        embedding_texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectors.astype("float32").tolist()
