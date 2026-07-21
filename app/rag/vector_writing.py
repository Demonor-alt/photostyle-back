"""Milvus 向量写入与文本构建服务"""  # 模块说明
from __future__ import annotations  # 启用未来注解语法

import json  # 引入json用于序列化元数据
import os  # 引入os用于读取环境变量
from datetime import datetime  # 引入datetime用于处理时间字段
from typing import Any  # 引入Any用于宽松类型标注

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility  # 引入Milvus官方SDK

from app.db.user_mapper import get_user_profile_by_id  # 引入用户读取服务
from app.db.history_mapper import get_history_record  # 引入历史查询服务
from app.utils.runtime import logger  # 引入统一日志器

_COLLECTION_NAME = os.getenv("MILVUS_COLLECTION_NAME", "photo_style_embeddings")  # 定义集合名称
_EMBEDDING_DIM = int(os.getenv("MILVUS_EMBEDDING_DIM", "768"))  # 定义向量维度
_CONNECTION_ALIAS = os.getenv("MILVUS_ALIAS", "default")  # 定义Milvus连接别名


def _safe_json_dumps(value: Any) -> str:  # 定义安全JSON序列化函数
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)  # 返回稳定的JSON字符串


def _safe_get(mapping: Any, key: str, default: Any = None) -> Any:  # 定义安全取值函数
    if isinstance(mapping, dict):  # 如果当前对象是字典
        return mapping.get(key, default)  # 直接按键取值
    return default  # 否则返回默认值


def _flatten_simple_analysis(value: Any) -> str:  # 将simple_analysis转成可向量化文本
    if not isinstance(value, dict):  # 如果不是字典
        return ""  # 返回空字符串
    parts: list[str] = []  # 定义文本片段列表
    for key in ["脸型", "线条感", "五官量感", "面部对比度", "肤色", "肤质", "气质"]:  # 遍历基础字段
        item = value.get(key)  # 取出字段值
        if item:  # 如果字段有值
            parts.append(f"{key}:{item}")  # 追加文本片段
    for section in ["眼睛", "眉毛", "鼻子", "嘴巴", "耳朵"]:  # 遍历五官分组
        section_value = value.get(section)  # 取出分组内容
        if isinstance(section_value, dict):  # 如果分组是字典
            for sub_key, sub_value in section_value.items():  # 遍历子字段
                if sub_value is not None and sub_value != "":  # 如果子字段有值
                    parts.append(f"{section}{sub_key}:{sub_value}")  # 追加文本片段
    style_vector = value.get("风格向量")  # 取出风格向量
    if isinstance(style_vector, dict):  # 如果风格向量是字典
        vector_text = ",".join(f"{k}:{v}" for k, v in style_vector.items())  # 拼接为字符串
        if vector_text:  # 如果拼接结果不为空
            parts.append(f"风格向量:{vector_text}")  # 追加风格向量文本
    return "；".join(parts)  # 用中文分号拼接全部片段


def _normalize_tags(value: Any) -> list[str]:  # 将标签统一规范为字符串数组
    if isinstance(value, list):  # 如果本来就是列表
        return [str(item).strip() for item in value if str(item).strip()]  # 转成字符串并过滤空项
    if isinstance(value, str) and value.strip():  # 如果是字符串且非空
        return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]  # 按逗号拆分
    return []  # 其他情况返回空列表


def _build_history_text(history: dict, user_profile: dict | None = None) -> str:  # 构建历史记录向量化文本
    input_data = history.get("input_data") or {}  # 取输入数据
    output_data = history.get("output_data") or {}  # 取输出数据
    simple_analysis = _safe_get(user_profile, "simple_analysis", {})  # 取用户简化分析
    comment = history.get("feedback_comment") or ""  # 取点评内容
    avg_score = history.get("avg_score")  # 取平均评分
    parts = [  # 组装文本片段
        f"风格:{_safe_get(input_data, 'style', '')}",  # 添加风格信息
        f"时间:{_safe_get(input_data, 'time', '')}",  # 添加时间信息
        f"地点:{_safe_get(input_data, 'location', '')}",  # 添加地点信息
        f"天气:{_safe_get(input_data, 'weather', '')}",  # 添加天气信息
        f"标签:{','.join(_normalize_tags(_safe_get(input_data, 'extra_tags', [])))}",  # 添加标签信息
        f"输入:{_safe_json_dumps(input_data)}",  # 添加输入JSON文本
        f"输出:{_safe_json_dumps(output_data)}",  # 添加输出JSON文本
        f"平均评分:{avg_score if avg_score is not None else ''}",  # 添加平均评分
        f"点评:{comment}",  # 添加评论内容
        f"用户画像:{_flatten_simple_analysis(simple_analysis)}",  # 添加用户画像文本
    ]  # 片段结束
    return "\n".join(part for part in parts if part)  # 拼接为多行文本


def _get_milvus_uri() -> str:  # 获取Milvus连接地址
    return os.getenv("MILVUS_URI", "http://localhost:19530")  # 返回默认连接地址


def _get_milvus_token() -> str | None:  # 获取Milvus认证信息
    token = os.getenv("MILVUS_TOKEN")  # 读取token
    return token if token else None  # 返回可用token或None


def _embedding_from_text(text: str) -> list[float]:  # 生成占位向量
    dimension = _EMBEDDING_DIM  # 读取向量维度
    if not text.strip():  # 如果文本为空
        return [0.0] * dimension  # 返回零向量
    values = [0.0] * dimension  # 初始化向量
    for index, char in enumerate(text):  # 遍历文本字符
        values[index % dimension] += (ord(char) % 97) / 97.0  # 使用字符码构建稳定向量
    norm = sum(v * v for v in values) ** 0.5  # 计算向量范数
    if norm == 0:  # 如果范数为零
        return values  # 直接返回
    return [round(v / norm, 6) for v in values]  # 归一化后返回


def build_photo_style_embedding_payload(history: dict, user_profile: dict | None = None) -> dict:  # 构建Milvus写入载荷
    text = _build_history_text(history, user_profile=user_profile)  # 生成可向量化文本
    embedding = _embedding_from_text(text)  # 生成向量
    input_data = history.get("input_data") or {}  # 取输入数据
    output_data = history.get("output_data") or {}  # 取输出数据
    tags = _normalize_tags(_safe_get(input_data, "extra_tags", []))  # 提取标签
    metadata = {  # 构造元数据
        "time": _safe_get(input_data, "time"),  # 写入时间
        "style": _safe_get(input_data, "style"),  # 写入风格
        "weather": _safe_get(input_data, "weather"),  # 写入天气
        "location": _safe_get(input_data, "location"),  # 写入地点
        "tags": tags,  # 写入标签
        "avg_score": history.get("avg_score"),  # 写入平均分
        "created_at": history.get("created_at") or datetime.utcnow().isoformat(),  # 写入创建时间
        "input_data": input_data,  # 保留输入快照
        "output_data": output_data,  # 保留输出快照
        "feedback_comment": history.get("feedback_comment"),  # 保留评论
        "simple_analysis": _safe_get(user_profile, "simple_analysis", {}),  # 保留用户画像
        "source": "history_feedback",  # 标记来源
    }  # 元数据结束
    return {  # 返回统一结构
        "user_id": history.get("user_id"),  # 返回用户ID
        "embedding": embedding,  # 返回向量
        "metadata": metadata,  # 返回元数据
        "text": text,  # 返回向量化文本
    }  # 返回结束


def _ensure_collection() -> Any:  # 确保集合存在
    connections.connect(alias=_CONNECTION_ALIAS, uri=_get_milvus_uri(), token=_get_milvus_token())  # 建立连接
    if utility.has_collection(_COLLECTION_NAME):  # 如果集合已存在
        return Collection(_COLLECTION_NAME)  # 直接返回集合对象
    fields = [  # 定义字段结构
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),  # 主键字段
        FieldSchema(name="user_id", dtype=DataType.INT64),  # 用户ID字段
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=_EMBEDDING_DIM),  # 向量字段
        FieldSchema(name="metadata", dtype=DataType.JSON),  # JSON元数据字段
    ]  # 字段结束
    schema = CollectionSchema(fields=fields, description="Photo style embeddings")  # 创建集合结构
    collection = Collection(name=_COLLECTION_NAME, schema=schema)  # 创建集合
    collection.create_index(  # 创建向量索引
        field_name="embedding",  # 指定向量字段
        index_params={"index_type": "HNSW", "metric_type": "COSINE", "params": {"M": 16, "efConstruction": 200}},  # 指定索引参数
    )  # 索引创建结束
    return collection  # 返回集合对象


def upsert_photo_style_embedding(history_id: int, user_id: int | None = None) -> dict:  # 写入或更新历史对应向量
    collection = _ensure_collection()  # 获取集合对象
    history = get_history_record(history_id)  # 读取当前历史记录
    user_profile = get_user_profile_by_id(user_id) if user_id is not None else None  # 读取用户画像
    payload = build_photo_style_embedding_payload(history, user_profile=user_profile)  # 构建向量载荷
    entity = [  # 组装待插入实体
        [payload["user_id"]],  # 用户ID列表
        [payload["embedding"]],  # 向量列表
        [json.dumps(payload["metadata"], ensure_ascii=False, default=str)],  # 元数据列表
    ]  # 实体结束
    collection.insert(data=entity)  # 执行插入
    collection.flush()  # 刷新落盘
    collection.load()  # 加载集合到内存，确保查询能立即看到新数据
    logger.info("milvus.embedding.saved history_id=%s user_id=%s", history_id, user_id)  # 记录保存日志
    return payload  # 返回载荷
