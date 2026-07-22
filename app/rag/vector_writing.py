"""Milvus 向量写入与文本构建服务。"""
from __future__ import annotations  # 启用注解的延迟求值，支持前向引用

import json  # JSON 序列化和反序列化
import os  # 操作系统环境变量和路径操作
from datetime import datetime  # 日期时间处理
from typing import Any  # 类型提示支持

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility  # Milvus 向量数据库客户端

from app.db.history_mapper import get_history_record  # 从数据库获取历史记录
from app.db.user_mapper import get_user_profile_by_id  # 从数据库获取用户长相
from app.rag.embedding import embed_text, get_embedding_dimension, get_embedding_model_name  # 文本向量化功能
from app.utils.runtime import logger  # 日志记录器

# Milvus collection 名称，默认存放照片风格推荐相关的历史记忆向量
_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "photo_style_embeddings")  # 从环境变量读取集合名称，默认为 photo_style_embeddings
# Milvus 连接别名，便于 pymilvus 在同一进程中复用连接
_CONNECTION_ALIAS = os.getenv("MILVUS_ALIAS", "default")  # 从环境变量读取连接别名，默认为 default
# Milvus 中保存 embedding 的向量字段名，检索模块会复用该字段名
_VECTOR_FIELD = "embedding"  # 定义向量字段名为 embedding


def _get_milvus_uri() -> str:  # 定义获取 Milvus URI 的函数
    """读取 Milvus 连接地址。"""
    return os.getenv("MILVUS_URI", "http://localhost:19530")  # 从环境变量读取 Milvus URI，默认为本地地址


def _get_milvus_token() -> str | None:  # 定义获取 Milvus 认证令牌的函数
    """读取 Milvus token；本地无认证时返回 None。"""
    token = os.getenv("MILVUS_TOKEN")  # 从环境变量读取 Milvus 认证令牌
    return token if token else None  # 如果令牌存在则返回，否则返回 None


def get_collection_name() -> str:  # 定义获取集合名称的公开函数
    """返回当前 RAG 使用的 Milvus collection 名称。"""
    return _COLLECTION_NAME  # 返回全局定义的集合名称


def get_vector_field_name() -> str:  # 定义获取向量字段名的公开函数
    """返回 Milvus 向量字段名。"""
    return _VECTOR_FIELD  # 返回全局定义的向量字段名


def get_connection_alias() -> str:  # 定义获取连接别名的公开函数
    """返回 Milvus 连接别名。"""
    return _CONNECTION_ALIAS  # 返回全局定义的连接别名


def _safe_json_dumps(value: Any) -> str:  # 定义安全的 JSON 序列化函数
    """将任意值稳定地序列化为中文友好的 JSON 字符串。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)  # 序列化为 JSON，不转义中文，键排序，无法序列化的值转为字符串


def _safe_get(mapping: Any, key: str, default: Any = None) -> Any:  # 定义安全的字典取值函数
    """只在对象是 dict 时取值，避免历史数据结构异常导致报错。"""
    if isinstance(mapping, dict):  # 检查对象是否为字典类型
        return mapping.get(key, default)  # 从字典中获取键值，不存在则返回默认值
    return default  # 如果不是字典，直接返回默认值


def _flatten_simple_analysis(value: Any) -> str:  # 定义将用户长相压平为文本的函数
    """将用户人脸压平成适合向量化的短文本。"""
    if not isinstance(value, dict):  # 检查输入是否为字典类型
        return ""  # 不是字典则返回空字符串
    parts: list[str] = []  # 初始化文本片段列表
    # 提取用户长相中的基础维度，作为后续个性化检索的重要语义特征
    for key in ["脸型", "线条感", "五官量感", "面部对比度", "肤色", "肤质", "气质"]:  # 遍历基础维度键名
        item = value.get(key)  # 获取该维度的值
        if item:  # 如果值存在
            parts.append(f"{key}:{item}")  # 将键值对格式化后添加到列表
    # 提取五官细节，帮助模型理解用户适合的妆造、姿势和拍摄角度
    for section in ["眼睛", "眉毛", "鼻子", "嘴巴", "耳朵"]:  # 遍历五官部位
        section_value = value.get(section)  # 获取该部位的详细信息
        if isinstance(section_value, dict):  # 检查部位信息是否为字典
            for sub_key, sub_value in section_value.items():  # 遍历部位的子属性
                if sub_value is not None and sub_value != "":  # 如果子属性值有效
                    parts.append(f"{section}{sub_key}:{sub_value}")  # 将部位子属性格式化后添加到列表
    # 风格向量是结构化偏好分数，转为文本后可以进入同一个语义空间
    style_vector = value.get("风格向量")  # 获取风格向量字典
    if isinstance(style_vector, dict):  # 检查风格向量是否为字典
        vector_text = ",".join(f"{k}:{v}" for k, v in style_vector.items())  # 将风格向量转为逗号分隔的键值对字符串
        if vector_text:  # 如果风格向量文本不为空
            parts.append(f"风格向量:{vector_text}")  # 添加到片段列表
    return "；".join(parts)  # 用分号连接所有文本片段并返回


def _normalize_tags(value: Any) -> list[str]:  # 定义标签规范化函数
    """将标签字段统一整理为字符串列表。"""
    if isinstance(value, list):  # 如果输入是列表
        return [str(item).strip() for item in value if str(item).strip()]  # 转为字符串并去除空白，过滤空值
    if isinstance(value, str) and value.strip():  # 如果输入是非空字符串
        return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]  # 将中文逗号替换为英文逗号，分割后去除空白
    return []  # 其他情况返回空列表


def _build_history_text(history: dict, user_profile: dict | None = None) -> str:  # 定义构建历史记录文本的函数
    """构建一条历史记录对应的入库文本。"""
    input_data = history.get("input_data") or {}  # 获取输入数据，不存在则使用空字典
    output_data = history.get("output_data") or {}  # 获取输出数据，不存在则使用空字典
    simple_analysis = _safe_get(user_profile, "simple_analysis", {})  # 安全获取用户长相分析数据
    comment = history.get("feedback_comment") or ""  # 获取反馈评论，不存在则使用空字符串
    avg_score = history.get("avg_score")  # 获取平均评分
    # 同时保留结构化摘要和完整输入/输出快照，让检索既能匹配场景，也能匹配历史推荐内容
    parts = [  # 构建文本片段列表
        f"风格:{_safe_get(input_data, 'style', '')}",  # 提取风格信息
        f"时间:{_safe_get(input_data, 'time', '')}",  # 提取时间信息
        f"地点:{_safe_get(input_data, 'location', '')}",  # 提取地点信息
        f"天气:{_safe_get(input_data, 'weather', '')}",  # 提取天气信息
        f"标签:{','.join(_normalize_tags(_safe_get(input_data, 'extra_tags', [])))}",  # 提取并规范化标签
        f"输入:{_safe_json_dumps(input_data)}",  # 将完整输入数据序列化为 JSON
        f"输出:{_safe_json_dumps(output_data)}",  # 将完整输出数据序列化为 JSON
        f"平均评分:{avg_score if avg_score is not None else ''}",  # 添加平均评分
        f"点评:{comment}",  # 添加用户点评
        f"用户长相:{_flatten_simple_analysis(simple_analysis)}",  # 添加压平后的用户长相
    ]
    return "\n".join(part for part in parts if part)  # 用换行符连接非空片段并返回


def connect_milvus() -> None:  # 定义建立 Milvus 连接的函数
    """建立 Milvus 连接；重复调用时 pymilvus 会复用同一 alias。"""
    connections.connect(alias=_CONNECTION_ALIAS, uri=_get_milvus_uri(), token=_get_milvus_token())  # 使用别名、URI 和令牌建立连接
    logger.info("Milvus 连接成功")


def build_photo_style_embedding_payload(history: dict, user_profile: dict | None = None) -> dict:  # 定义构建向量载荷的函数
    """将历史记录和用户长相转换为可写入 Milvus 的统一载荷。"""
    text = _build_history_text(history, user_profile=user_profile)  # 构建历史记录的文本表示
    logger.debug("历史文本构建完成，文本：%s", text)
    # 文档入库使用原文向量，不添加查询前缀
    embedding = embed_text(text)  # 将文本转换为向量
    logger.info("文本向量化完成，向量维度=%d", len(embedding))
    input_data = history.get("input_data") or {}  # 获取输入数据
    output_data = history.get("output_data") or {}  # 获取输出数据
    tags = _normalize_tags(_safe_get(input_data, "extra_tags", []))  # 规范化标签
    history_id = int(history["id"])  # 获取历史记录 ID
    user_id = int(history["user_id"])  # 获取用户 ID
    avg_score = history.get("avg_score")  # 获取平均评分
    # metadata 保留可过滤字段和完整快照，便于检索、重排序和问题排查
    metadata = {  # 构建元数据字典
        "history_id": history_id,  # 历史记录 ID
        "doc_type": "history_feedback",  # 文档类型标记为历史反馈
        "time": _safe_get(input_data, "time"),  # 时间信息
        "style": _safe_get(input_data, "style"),  # 风格信息
        "weather": _safe_get(input_data, "weather"),  # 天气信息
        "location": _safe_get(input_data, "location"),  # 地点信息
        "tags": tags,  # 标签列表
        "avg_score": avg_score,  # 平均评分
        "is_positive_feedback": avg_score is not None and float(avg_score) >= 4.0,  # 判断是否为正向反馈（评分>=4.0）
        "created_at": history.get("created_at") or datetime.utcnow().isoformat(),  # 创建时间，不存在则使用当前时间
        "updated_at": datetime.utcnow().isoformat(),  # 更新时间为当前时间
        "input_data": input_data,  # 完整输入数据快照
        "output_data": output_data,  # 完整输出数据快照
        "feedback_comment": history.get("feedback_comment"),  # 用户反馈评论
        "simple_analysis": _safe_get(user_profile, "simple_analysis", {}),  # 用户长相分析
        "source": "history_feedback",  # 数据来源标记
        "embedding_model": get_embedding_model_name(),  # 使用的向量模型名称
    }
    return {  # 返回完整的载荷字典
        "history_id": history_id,  # 历史记录 ID
        "user_id": user_id,  # 用户 ID
        "embedding": embedding,  # 向量数据
        "metadata": metadata,  # 元数据
    }


def _ensure_collection() -> Collection:
    """确保 Milvus collection 存在，并校验向量维度与当前 BGE 模型一致。"""
    connect_milvus()
    embedding_dim = get_embedding_dimension()
    if utility.has_collection(_COLLECTION_NAME):
        collection = Collection(_COLLECTION_NAME)
        vector_field = next((field for field in collection.schema.fields if field.name == _VECTOR_FIELD), None)
        if vector_field is not None and vector_field.params.get("dim") != embedding_dim:
            logger.error("向量维度不匹配，collection dim=%s, embedding dim=%s", vector_field.params.get("dim"), embedding_dim)
            raise RuntimeError(
                f"Milvus collection '{_COLLECTION_NAME}' dim={vector_field.params.get('dim')} "
                f"与当前 embedding dim={embedding_dim} 不一致，请迁移或重建 collection"
            )
        logger.info("使用已存在的 collection，向量维度=%s", embedding_dim)
        return collection

    logger.info("collection 不存在，开始创建新 collection，向量维度=%s", embedding_dim)
    # 新 collection 显式保存 history_id、user_id、doc_type，方便过滤和去重；完整上下文保留在 metadata 中。
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="history_id", dtype=DataType.INT64),
        FieldSchema(name="user_id", dtype=DataType.INT64),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name=_VECTOR_FIELD, dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
        FieldSchema(name="metadata", dtype=DataType.JSON),
    ]
    schema = CollectionSchema(fields=fields, description="Photo style embeddings")
    collection = Collection(name=_COLLECTION_NAME, schema=schema)
    # HNSW 适合中小规模向量检索，COSINE 与归一化 BGE 向量匹配。
    collection.create_index(
        field_name=_VECTOR_FIELD,
        index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},
    )
    # 标量索引用于提升按历史 ID 和用户 ID 过滤的效率。
    collection.create_index(field_name="history_id", index_name="idx_history_id")
    collection.create_index(field_name="user_id", index_name="idx_user_id")
    collection.load()
    logger.info("新 collection 创建完成，已建立向量索引和标量索引")
    return collection


def _delete_existing_history_embedding(collection: Collection, history_id: int, user_id: int) -> None:
    """删除同一用户同一历史记录的旧向量，保证 upsert 不产生重复记忆。防止RabbitMQ 任务重复消费。"""
    expr = f"history_id == {history_id} and user_id == {user_id} and doc_type == 'history_feedback'"
    logger.info("正在删除旧向量记录: %s", expr)
    try:
        result = collection.delete(expr)
        collection.flush()
        logger.info("旧向量删除成功 expr=%s result=%s", expr, result)
    except Exception:
        logger.exception("删除旧向量失败 expr=%s", expr)
        raise


def upsert_photo_style_embedding(history_id: int, user_id: int | None = None) -> dict:
    """为指定历史记录写入或更新向量记忆。"""
    logger.info("开始处理向量写入，history_id=%s user_id=%s", history_id, user_id)
    collection = _ensure_collection()
    history = get_history_record(history_id)
    resolved_user_id = int(user_id if user_id is not None else history["user_id"])
    logger.debug("解析用户ID完成，resolved_user_id=%s", resolved_user_id)
    user_profile = get_user_profile_by_id(resolved_user_id)
    payload = build_photo_style_embedding_payload(history, user_profile=user_profile)

    # 先删旧记录再插入新记录，修正原本 insert-only 导致的重复向量问题。
    _delete_existing_history_embedding(collection, payload["history_id"], payload["user_id"])
    logger.info("开始插入新向量数据")
    entity = [
        [payload["history_id"]],
        [payload["user_id"]],
        [payload["metadata"]["doc_type"]],
        [payload["embedding"]],
        [payload["metadata"]],
    ]
    collection.insert(data=entity)
    collection.flush()
    logger.info(
        "向量写入成功 history_id=%s user_id=%s model=%s",
        payload["history_id"],
        payload["user_id"],
        payload["metadata"]["embedding_model"],
    )
    return payload
