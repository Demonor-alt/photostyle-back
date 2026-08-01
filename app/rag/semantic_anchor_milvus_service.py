"""Semantic Anchor Library 的 Milvus 独立服务封装。"""  # 模块说明：Semantic Anchor Library 的 Milvus 独立服务封装。
from __future__ import annotations  # 启用延迟求值的类型注解支持。

import os  # 读取环境变量与系统配置。
from typing import Any  # 提供通用类型标注。

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, utility  # 引入 Milvus 相关核心能力。

from app.rag.embedding import embed_text, get_embedding_dimension, get_embedding_model_name  # 引入向量化与模型信息工具。
from app.rag.milvus_client import connect_milvus  # 复用通用 Milvus 连接与字段配置。
from app.schemas.dto.semantic_anchor_dto import SearchSimilarAnchorRequest, SearchSimilarAnchorResponse  # 引入语义锚点检索 DTO。
from app.utils.runtime import logger  # 引入运行时日志对象。
from app.utils.semantic_anchors import get_semantic_axis_names  # 引入语义轴配置工具。

# Semantic Anchor Library 是全局语义知识库，不保存用户私有画像数据。
_COLLECTION_NAME = os.getenv("SEMANTIC_AXIS_COLLECTION_NAME")  # 语义轴集合名称
_VECTOR_FIELD = "embedding" # 向量字段名。
_DEFAULT_SEARCH_PARAMS = {"metric_type": "COSINE", "params": {"ef": 64}}  # 默认相似度搜索参数。
_SEMANTIC_AXIS_NAMES = get_semantic_axis_names()  # 语义轴名称列表。

def _ensure_axis_configured(axis_name: str) -> None:  # 检查语义轴是否存在的内部函数。
    """校验 axis 是否来自配置，避免服务代码写死固定分类。"""  # 函数文档：校验 axis 配置。
    if axis_name not in _SEMANTIC_AXIS_NAMES:  # 如果给定轴名不在配置中。
        raise ValueError(f"未知语义轴: {axis_name}，请先在 semantic_axes.yaml 中配置")  # 抛出未知轴异常。


def _ensure_collection() -> Collection:  # 确保集合存在并返回集合对象的内部函数。
    """确保 semantic_axis_library collection 存在，并校验向量维度。"""  # 函数文档：确保集合存在。
    connect_milvus()  # 先建立 Milvus 连接。
    embedding_dim = get_embedding_dimension()  # 获取当前 embedding 维度。
    if utility.has_collection(_COLLECTION_NAME):  # 如果集合已经存在。
        collection = Collection(_COLLECTION_NAME)  # 打开已有集合。
        vector_field = next((field for field in collection.schema.fields if field.name == _VECTOR_FIELD), None)  # 查找向量字段。
        if vector_field is not None and vector_field.params.get("dim") != embedding_dim:  # 如果维度与当前模型不一致。
            raise RuntimeError(
                f"Milvus collection '{_COLLECTION_NAME}' dim={vector_field.params.get('dim')} "
                f"与当前 embedding dim={embedding_dim} 不一致，请迁移或重建 collection"
            )  # 抛出维度不一致异常。
        collection.load()  # 加载集合到内存。
        return collection  # 返回已有集合对象。

    fields = [  # 定义新集合的字段列表。
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),  # 主键字段，自动生成 ID。
        FieldSchema(name="axis_name", dtype=DataType.VARCHAR, max_length=64),  # 语义轴名称字段。
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),  # 文本内容字段。
        FieldSchema(name=_VECTOR_FIELD, dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),  # 向量字段，维度取决于 embedding 模型。
        FieldSchema(name="axis_value", dtype=DataType.FLOAT),  # 轴值字段。
        FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=128),  # 类别字段。
    ]  # 字段列表定义结束。
    schema = CollectionSchema(fields=fields, description="Global semantic axis anchor library")  # 构建集合 schema。
    collection = Collection(name=_COLLECTION_NAME, schema=schema)  # 创建新的集合。
    collection.create_index(  # 为向量字段创建索引。
        field_name=_VECTOR_FIELD,  # 指定索引字段名。
        index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},  # 设置 HNSW 索引参数。
    )  # 索引创建结束。
    collection.create_index(field_name="axis_name", index_name="idx_semantic_axis_name")  # 为 axis_name 创建索引。
    collection.load()  # 加载新集合。
    logger.info("semantic_anchor.collection.created name=%s dim=%s", _COLLECTION_NAME, embedding_dim)  # 记录集合创建日志。
    return collection  # 返回集合对象。


def insert_anchors(anchors: list[dict[str, Any]]) -> None:  # 定义批量插入语义锚点的函数。
    """向全局 Semantic Anchor Library 批量插入语义锚点。"""  # 函数文档：说明该函数用于批量写入全局语义锚点库。
    if not anchors:  # 如果传入的锚点列表为空。
        return  # 直接返回，不执行后续插入逻辑。

    normalized: list[dict[str, Any]] = []  # 初始化标准化后的锚点数据列表。
    for index, anchor in enumerate(anchors, start=1):  # 遍历输入锚点，并从 1 开始记录序号。
        axis_name = str(anchor.get("axis_name", "")).strip()  # 提取并清理语义轴名称。
        text = str(anchor.get("text", "")).strip()  # 提取并清理锚点文本。
        if not text:  # 如果锚点文本为空。
            raise ValueError(f"第 {index} 条 semantic anchor text cannot be empty")  # 抛出异常提示对应序号的文本不能为空。
        _ensure_axis_configured(axis_name)  # 校验该语义轴是否已在配置中定义。
        normalized.append(  # 将处理后的锚点追加到标准化列表。
            {  # 构造单条标准化锚点数据。
                "axis_name": axis_name,  # 保存语义轴名称。
                "text": text,  # 保存锚点文本。
                "embedding": embed_text(text),  # 生成并保存锚点文本的向量表示。
                "axis_value": float(anchor.get("axis_value", 0)),  # 提取语义轴数值并转换为浮点数。
                "category": str(anchor.get("category", "")).strip(),  # 提取并清理锚点分类。
            }  # 单条标准化锚点数据构造结束。
        )  # 追加标准化锚点数据结束。
    collection = _ensure_collection()  # 获取或创建 Milvus 语义锚点集合。
    entity = [  # 按 Milvus 插入格式组织字段列数据。
        [anchor["axis_name"] for anchor in normalized],  # 收集所有锚点的语义轴名称列。
        [anchor["text"] for anchor in normalized],  # 收集所有锚点的文本列。
        [anchor["embedding"] for anchor in normalized],  # 收集所有锚点的向量列。
        [anchor["axis_value"] for anchor in normalized],  # 收集所有锚点的语义轴数值列。
        [anchor["category"] for anchor in normalized],  # 收集所有锚点的分类列。
    ]  # 字段列数据组织完成。
    collection.insert(data=entity)  # 将字段列数据批量插入 Milvus 集合。
    collection.flush()  # 刷新集合，确保插入数据持久化可见。
    logger.info(  # 记录批量插入成功的日志。
        "semantic_anchor.inserted_batch count=%s model=%s",  # 日志模板：包含插入数量和嵌入模型名称。
        len(normalized),  # 记录本次插入的标准化锚点数量。
        get_embedding_model_name(),  # 记录当前使用的嵌入模型名称。
    )  # 日志记录调用结束。


def _build_filter_expr(filters: dict[str, Any] | None = None) -> str | None:  # 构建过滤表达式的内部函数。
    """根据可选条件构造全局语义锚点过滤表达式。"""  # 函数文档：构建过滤表达式。
    filters = filters or {}  # 如果未传入过滤条件，则使用空字典。
    clauses: list[str] = []  # 用于收集每个过滤子句。
    axis_name = filters.get("axis_name")  # 读取 axis_name 过滤项。
    if axis_name:  # 如果 axis_name 存在。
        _ensure_axis_configured(str(axis_name))  # 先校验该 axis 是否在配置中。
        clauses.append(f"axis_name == '{_escape_expr_string(str(axis_name))}'")  # 生成 axis_name 过滤条件。
    category = filters.get("category")  # 读取 category 过滤项。
    if category:  # 如果 category 存在。
        clauses.append(f"category == '{_escape_expr_string(str(category))}'")  # 生成 category 过滤条件。
    return " and ".join(clauses) if clauses else None  # 有条件则拼接，否则返回 None。


def _escape_expr_string(value: str) -> str:  # 转义表达式字符串的内部函数。
    """转义 Milvus 表达式中的字符串。"""  # 函数文档：转义表达式字符串。
    return value.replace("\\", "\\\\").replace("'", "\\'")  # 先转义反斜杠，再转义单引号。


def search_similar_anchor(request: SearchSimilarAnchorRequest) -> SearchSimilarAnchorResponse:  # 返回匹配结果。
    """在全局 Semantic Anchor Library 中检索相似语义锚点。"""  # 函数文档：检索相似锚点。
    query_text = request.query_text.strip()  # 去掉查询文本首尾空白。
    if not query_text:  # 如果查询为空。
        return SearchSimilarAnchorResponse(anchors=[])  # 直接返回空结果。

    collection = _ensure_collection()  # 获取或创建集合。
    expr = _build_filter_expr(request.filters)  # 根据过滤条件构建表达式。
    search_result = collection.search(  # 执行向量搜索。
        data=[embed_text(query_text, for_query=True)],  # 将查询文本编码为查询向量。
        anns_field=_VECTOR_FIELD,  # 指定向量字段。
        param=_DEFAULT_SEARCH_PARAMS,  # 指定搜索参数。
        limit=request.top_k,  # 限制返回数量。
        expr=expr,  # 传入过滤表达式。
        output_fields=["id", "axis_name", "text", "axis_value", "category"],  # 指定输出字段。
    )  # 搜索调用结束。

    anchors: list[dict[str, Any]] = []  # 存放最终结果。
    for hit in search_result[0]:  # 遍历第一组搜索结果。
        score = float(hit.score)  # 提取相似度分数。
        if request.min_score is not None and score < request.min_score:  # 如果低于最小分数阈值。
            continue  # 跳过该结果。
        entity = hit.entity  # 获取命中的实体。
        anchors.append(  # 将结果整理成字典后追加。
            {
                "id": entity.get("id"),  # 实体 ID。
                "axis_name": entity.get("axis_name"),  # 轴名。
                "text": entity.get("text"),  # 文本。
                "axis_value": entity.get("axis_value"),  # 轴值。
                "category": entity.get("category"),  # 类别。
                "score": score,  # 相似度分数。
            }  # 单条结果字典结束。
        )  # 结果追加结束。

    logger.info("semantic_anchor.searched top_k=%s returned=%s expr=%s", request.top_k, len(anchors), expr)  # 记录搜索日志。
    return SearchSimilarAnchorResponse(anchors=anchors)  # 返回搜索结果。
