"""Milvus 向量检索服务。"""
from __future__ import annotations

from typing import Any

from pymilvus import Collection, utility

from app.rag.embedding import embed_text, get_embedding_model_name
from app.rag.vector_writing import (
    connect_milvus,
    get_collection_name,
)
from app.rag.milvus_client import ( get_vector_field_name )  # 复用通用 Milvus 客户端
from app.schemas.dto.semantic_anchor_dto import PhotoStyleMemorySearchResult  # 引入照片风格历史记忆检索结果 DTO。
from app.utils.runtime import logger

# HNSW 检索参数；ef 越高召回越好但延迟越高，当前值适合作为业务默认值。
_DEFAULT_SEARCH_PARAMS = {"metric_type": "COSINE", "params": {"ef": 64}}


def _get_collection() -> Collection:
    """获取并加载 Milvus collection。"""
    connect_milvus()
    collection_name = get_collection_name()
    if not utility.has_collection(collection_name):
        raise RuntimeError(f"Milvus collection '{collection_name}' 不存在，请先写入向量数据")
    collection = Collection(collection_name)
    collection.load()
    return collection


def _escape_expr_string(value: str) -> str:
    """转义 Milvus 表达式中的字符串，避免单引号或反斜杠破坏过滤表达式。"""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _build_filter_expr(user_id: int, filters: dict[str, Any] | None = None) -> str:
    """根据用户 ID 和业务过滤条件构造 Milvus 标量过滤表达式。"""
    # 用户隔离是强制条件，避免检索到其他用户的私有历史记忆。
    clauses = [f"user_id == {int(user_id)}"]
    filters = filters or {}

    # 默认只检索历史反馈记忆，后续如果加入知识库可通过 doc_type 扩展。
    doc_type = filters.get("doc_type", "history_feedback")
    if doc_type:
        clauses.append(f"doc_type == '{_escape_expr_string(str(doc_type))}'")

    # 根据评分过滤，常用于只召回高质量或高满意度历史案例。
    min_avg_score = filters.get("min_avg_score")
    if min_avg_score is not None:
        clauses.append(f"metadata['avg_score'] >= {float(min_avg_score)}")

    # 指定历史 ID 时可用于检查单条记录是否已写入向量库。
    history_id = filters.get("history_id")
    if history_id is not None:
        clauses.append(f"history_id == {int(history_id)}")

    # 正负反馈过滤，便于分别构建“可参考偏好”和“需要避免的偏好”。
    only_positive = filters.get("only_positive")
    if only_positive is True:
        clauses.append("metadata['is_positive_feedback'] == true")
    elif only_positive is False:
        clauses.append("metadata['is_positive_feedback'] == false")

    # 风格、天气、地点属于强业务条件，可缩小召回范围并减少噪声。
    style = filters.get("style")
    if style:
        clauses.append(f"metadata['style'] == '{_escape_expr_string(str(style))}'")

    weather = filters.get("weather")
    if weather:
        clauses.append(f"metadata['weather'] == '{_escape_expr_string(str(weather))}'")

    location = filters.get("location")
    if location:
        clauses.append(f"metadata['location'] == '{_escape_expr_string(str(location))}'")

    return " and ".join(clauses)


def search_photo_style_memories(
    user_id: int,
    query_text: str,
    top_k: int = 5,
    min_score: float | None = None,
    filters: dict[str, Any] | None = None,
) -> list[PhotoStyleMemorySearchResult]:
    """检索与当前 query 最相关的用户照片风格历史记忆。"""
    if not query_text.strip():
        return []

    collection = _get_collection()
    # 查询侧使用 BGE 查询前缀，提升检索场景下的语义匹配效果。
    query_embedding = embed_text(query_text, for_query=True)
    expr = _build_filter_expr(user_id, filters)
    limit = max(1, int(top_k))
    search_result = collection.search(
        data=[query_embedding],
        anns_field=get_vector_field_name(),
        param=_DEFAULT_SEARCH_PARAMS,
        limit=limit,
        expr=expr,
        output_fields=["id", "history_id", "user_id", "doc_type", "text", "metadata"],
    )

    memories: list[PhotoStyleMemorySearchResult] = []
    for hit in search_result[0]:
        score = float(hit.score)
        # min_score 用于丢弃弱相关结果，避免低质量上下文污染 LLM prompt。
        if min_score is not None and score < min_score:
            continue
        entity = hit.entity
        metadata = entity.get("metadata") or {}
        memories.append(
            PhotoStyleMemorySearchResult(
                id=entity.get("id"),
                history_id=entity.get("history_id"),
                user_id=entity.get("user_id"),
                doc_type=entity.get("doc_type"),
                text=entity.get("text"),
                metadata=metadata,
                score=score,
            )
        )

    logger.info(
        "milvus.embedding.searched user_id=%s top_k=%s returned=%s expr=%s model=%s",
        user_id,
        top_k,
        len(memories),
        expr,
        get_embedding_model_name(),
    )
    return memories
