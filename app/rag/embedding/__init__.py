"""RAG embedding 能力导出。"""

# 统一从这里导出 embedding 能力，其他 RAG 模块无需关心底层模型实现。
from app.rag.embedding.bge_client import (
    embed_text,
    embed_texts,
    get_embedding_dimension,
    get_embedding_model_name,
)

# 限制包级别可公开导出的符号，避免外部依赖内部实现细节。
__all__ = [
    "embed_text",
    "embed_texts",
    "get_embedding_dimension",
    "get_embedding_model_name",
]
