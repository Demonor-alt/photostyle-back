"""用户偏好分析服务。"""  # 模块说明：负责分析用户评论并生成偏好画像更新结果。
from __future__ import annotations  # 启用前向引用类型注解。

import json  # 用于 JSON 序列化。
import os  # 用于读取环境变量。
from typing import Any  # 用于表示任意类型。

import dashscope  # 引入 DashScope SDK。
from dashscope import Generation  # 引入文本生成能力。
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

from app.rag.semantic_anchor_milvus_service import search_similar_anchor  # 引入 Milvus 语义锚点检索方法。
from app.services.llm.qwen_client import get_api_key, get_qwen_response_message
from app.utils.runtime import logger


# 配置 DashScope 百炼 API 地址，保持和现有 Qwen 服务一致。  # 让 SDK 指向正确的服务地址。
dashscope.base_http_api_url = os.getenv("DASHSCOPE_API_URL")  # 设置 DashScope 基础 API 地址。

DEFAULT_ANCHOR_TOP_K = os.getenv("DEFAULT_ANCHOR_TOP_K")  #默认召回语义锚点数量


class PreferenceAxisUpdateOutput(BaseModel):
    axis_name: str = Field(default="")
    value: float = Field(default=0.0)
    confidence: float = Field(default=0.0)
    reason: str = Field(default="")


class PreferenceAnalysisOutput(BaseModel):
    axis_updates: list[PreferenceAxisUpdateOutput] = Field(default_factory=list)
    avoid_patterns: list[str] = Field(default_factory=list)
    success_patterns: list[str] = Field(default_factory=list)


_PREFERENCE_ANALYSIS_PARSER = PydanticOutputParser(pydantic_object=PreferenceAnalysisOutput)


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    return content if isinstance(content, str) else str(content)


def _safe_json_dumps(value: Any) -> str:  # 将任意对象安全序列化为 JSON 字符串。
    """将任意业务对象稳定序列化为中文 JSON 字符串。"""  # 说明该函数用于稳定序列化。
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)  # 保留中文并保证字段顺序。



def _clamp(value: Any, min_value: float, max_value: float, default: float = 0.0) -> float:  # 将数值限制在区间内。
    """将数值安全限制在指定区间。"""  # 说明该函数用于数值边界控制。
    try:  # 尝试转成浮点数。
        number = float(value)  # 将输入转换为浮点数。
    except Exception:  # 任何异常都使用默认值。
        number = default  # 使用默认数值。
    if number < min_value:  # 如果小于下限。
        return min_value  # 返回下限。
    if number > max_value:  # 如果大于上限。
        return max_value  # 返回上限。
    return round(number, 4)  # 保留 4 位小数。


def _normalize_anchor(anchor: dict[str, Any]) -> dict[str, Any]:  # 标准化语义锚点字段。
    """整理 Milvus 召回锚点，只保留 LLM 判断需要的字段。"""  # 说明只保留必要字段。
    return {  # 构造标准化后的锚点。
        "id": anchor.get("id"),  # 锚点 ID。
        "axis_name": anchor.get("axis_name"),  # 语义轴名称。
        "text": anchor.get("text"),  # 锚点文本。
        "axis_value": anchor.get("axis_value"),  # 语义轴取值。
        "category": anchor.get("category"),  # 分类信息。
        "similarity": _clamp(anchor.get("score"), 0.0, 1.0),  # 相似度分数并限制在 0 到 1。
    }  # 返回标准化结果。


def _search_semantic_anchors(comment: str, top_k: int) -> list[dict[str, Any]]:  # 根据评论检索语义锚点。
    """使用评论文本向量检索全局 Semantic Anchor Library。"""  # 说明调用向量检索。
    anchors = search_similar_anchor(query_text=comment, top_k=top_k)  # 执行相似锚点搜索。
    normalized = [_normalize_anchor(anchor) for anchor in anchors]  # 将锚点逐条标准化。
    logger.info("preference.semantic_anchors.recalled count=%s", len(normalized))  # 记录召回数量。
    return normalized  # 返回标准化锚点列表。


def _best_similarity_by_axis(anchors: list[dict[str, Any]]) -> dict[str, float]:  # 统计每个轴的最佳相似度。
    """按 axis 聚合最高 Milvus 相似度，用于最终 confidence 融合。"""  # 说明用途是融合置信度。
    result: dict[str, float] = {}  # 初始化结果字典。
    for anchor in anchors:  # 遍历所有锚点。
        axis_name = str(anchor.get("axis_name") or "").strip()  # 读取并清理轴名称。
        if not axis_name:  # 如果轴名称为空。
            continue  # 跳过该项。
        similarity = _clamp(anchor.get("similarity"), 0.0, 1.0)  # 获取并限制相似度。
        result[axis_name] = max(result.get(axis_name, 0.0), similarity)  # 保留该轴最高相似度。
    return result  # 返回按轴聚合后的结果。


def _build_llm_messages(  # 构造发送给大模型的消息列表。
    *,  # 强制使用关键字参数。
    user_id: int,  # 用户 ID。
    comment: str,  # 用户评论。
    anchors: list[dict[str, Any]],  # 语义锚点列表。
    history_scores: Any,  # 历史评分。
    history_profile: Any,  # 历史画像。
) -> list[dict[str, str]]:  # 返回聊天消息列表。
    """构造偏好分析 LLM 输入。"""  # 说明该函数用于拼接大模型输入。
    user_payload = {  # 构造用户侧输入负载。
        "user_id": user_id,  # 写入用户 ID。
        "comment": comment,  # 写入用户评论。
        "semantic_anchor_recall": anchors,  # 写入召回锚点。
        "history_profile": history_profile or {},  # 写入历史画像，空时用空对象。
        "history_scores": history_scores or {},  # 写入历史评分，空时用空对象。
        "output_schema": {  # 定义输出格式。
            "axis_updates": [  # 语义轴更新列表。
                {  # 单个更新结构。
                    "axis_name": "string，必须来自 semantic_anchor_recall 中召回到的 axis_name 或历史画像中已有 axis_name",  # 轴名称要求。
                    "value": "number，范围 -1 到 1，负数表示降低/拒绝，正数表示增强/喜欢",  # 更新值要求。
                    "confidence": "number，范围 0 到 1，表示 LLM 对该判断本身的置信度，不要融合 Milvus similarity",  # 置信度要求。
                    "reason": "string，简短中文原因",  # 原因要求。
                }  # 单项 schema 结束。
            ],  # axis_updates 定义结束。
            "avoid_patterns": ["string，用户应避免的偏好模式"],  # 避雷模式列表。
            "success_patterns": ["string，用户正向偏好的成功模式"],  # 成功模式列表。
        },  # 输出 schema 结束。
    }  # 用户负载结束。
    system_prompt = (  # 构造系统提示词。
        "你是用户审美偏好分析服务。请根据用户评论、Milvus 语义锚点召回结果、历史画像和历史评分，"  # 第一段说明任务。
        "推断用户偏好的语义轴更新。不要使用固定关键词规则，只能基于输入证据做判断。"  # 约束推理方式。
        "请严格只输出 JSON，不要输出解释、Markdown 或代码块。"  # 要求输出格式。
        f"请遵循以下格式要求：{_PREFERENCE_ANALYSIS_PARSER.get_format_instructions()}"  # LangChain解析器格式要求。
        "JSON 字段必须包含 axis_updates、avoid_patterns、success_patterns。"  # 要求字段完整。
        "axis_updates 中 confidence 表示你对判断的置信度，范围 0 到 1，不要自行融合 Milvus similarity。"  # 置信度说明。
    )  # 系统提示词结束。
    return [  # 返回消息列表。
        {"role": "system", "content": system_prompt},  # 系统消息。
        {"role": "user", "content": _safe_json_dumps(user_payload)},  # 用户消息，内容为 JSON。
    ]  # 消息列表结束。


def _normalize_llm_result(payload: PreferenceAnalysisOutput) -> dict[str, Any]:  # 标准化大模型输出。
    """规范 LLM 输出结构，保证服务返回稳定。"""  # 说明该函数用于统一返回格式。
    raw_updates = [item.model_dump() for item in payload.axis_updates]  # 读取Pydantic更新列表。
    axis_updates: list[dict[str, Any]] = []  # 初始化清洗后的更新列表。
    if isinstance(raw_updates, list):  # 仅处理列表类型。
        for item in raw_updates:  # 遍历每条更新。
            if not isinstance(item, dict):  # 非字典项直接忽略。
                continue  # 跳过。
            axis_name = str(item.get("axis_name", "")).strip()  # 获取并清理轴名称。
            if not axis_name:  # 空名称忽略。
                continue  # 跳过。
            axis_updates.append(  # 追加标准化后的记录。
                {  # 单条标准化记录。
                    "axis_name": axis_name,  # 标准化轴名。
                    "value": _clamp(item.get("value"), -1.0, 1.0),  # 标准化值域。
                    "llm_confidence": _clamp(item.get("confidence"), 0.0, 1.0),  # 标准化大模型置信度。
                    "reason": str(item.get("reason", "")).strip(),  # 标准化原因文本。
                }  # 单条记录结束。
            )  # 追加结束。

    def normalize_patterns(value: Any) -> list[str]:  # 内部函数：规范字符串列表。
        if not isinstance(value, list):  # 非列表直接返回空。
            return []  # 返回空列表。
        return [str(item).strip() for item in value if str(item).strip()]  # 过滤空字符串并清理空白。

    return {  # 返回统一结构。
        "axis_updates": axis_updates,  # 语义轴更新。
        "avoid_patterns": normalize_patterns(payload.avoid_patterns),  # 避雷模式。
        "success_patterns": normalize_patterns(payload.success_patterns),  # 成功模式。
    }  # 返回结束。


def _merge_confidence(axis_updates: list[dict[str, Any]], similarity_by_axis: dict[str, float]) -> list[dict[str, Any]]:  # 融合置信度。
    """按照 confidence = LLM判断 * 0.6 + Milvus similarity * 0.4 计算最终置信度。"""  # 说明融合公式。
    merged: list[dict[str, Any]] = []  # 初始化融合结果。
    for update in axis_updates:  # 遍历每条轴更新。
        axis_name = update["axis_name"]  # 读取轴名称。
        llm_confidence = _clamp(update.get("llm_confidence"), 0.0, 1.0)  # 获取 LLM 置信度。
        milvus_similarity = _clamp(similarity_by_axis.get(axis_name, 0.0), 0.0, 1.0)  # 获取 Milvus 相似度。
        confidence = round(llm_confidence * 0.6 + milvus_similarity * 0.4, 4)  # 按权重融合置信度。
        merged.append(  # 追加融合结果。
            {  # 单条融合记录。
                "axis_name": axis_name,  # 轴名称。
                "value": update["value"],  # 更新值。
                "confidence": confidence,  # 最终置信度。
                "reason": update["reason"],  # 原因说明。
                "llm_confidence": llm_confidence,  # 保留 LLM 置信度。
                "milvus_similarity": milvus_similarity,  # 保留 Milvus 相似度。
            }  # 单条记录结束。
        )  # 追加结束。
    return merged  # 返回融合结果。


def analyze_user_preference(  # 对单个用户评论进行偏好分析。
    *,  # 强制关键字传参。
    user_id: int,  # 用户 ID。
    comment: str,  # 用户评论。
    history_scores: Any | None = None,  # 历史评分。
    history_profile: Any | None = None,  # 历史画像。
    top_k: int = DEFAULT_ANCHOR_TOP_K,  # 召回数量。
) -> dict[str, Any]:  # 返回结构化分析结果。
    """分析用户评论中的偏好变化，返回结构化结果但不写数据库。"""  # 说明该函数只分析不落库。
    comment = comment.strip()  # 去掉评论首尾空白。
    if not comment:  # 如果评论为空。
        return {"user_id": user_id, "axis_updates": [], "avoid_patterns": [], "success_patterns": [], "semantic_anchors": []}  # 返回空结果。

    api_key = get_api_key()  # 读取并校验 API Key。

    anchors = _search_semantic_anchors(comment, top_k=max(1, int(top_k)))  # 检索语义锚点。
    similarity_by_axis = _best_similarity_by_axis(anchors)  # 计算每个轴的最佳相似度。
    messages = _build_llm_messages(  # 组装大模型消息。
        user_id=user_id,  # 用户 ID。
        comment=comment,  # 用户评论。
        anchors=anchors,  # 召回锚点。
        history_scores=history_scores,  # 历史评分。
        history_profile=history_profile,  # 历史画像。
    )  # 消息组装结束。
    logger.info(  # 记录请求信息。
        "preference.analysis.request user_id=%s comment=%s anchors=%s",  # 日志模板。
        user_id,  # 用户 ID。
        comment,  # 评论内容。
        _safe_json_dumps(anchors),  # 锚点 JSON。
    )  # 日志记录结束。
    response = Generation.call(  # 调用 Qwen 生成接口。
        api_key=api_key,  # 传入 API Key。
        model="qwen3-max",  # 选择模型。
        messages=messages,  # 传入消息列表。
        result_format="message",  # 结果格式为 message。
        enable_thinking=True,  # 开启思考能力。
    )  # 请求结束。
    message = get_qwen_response_message(response)  # 统一判断Qwen响应并提取message。
    if message is None:  # 响应失败时抛出可读异常。
        raise RuntimeError(f"Qwen 偏好分析调用失败，response={response}")  # 暴露调用失败信息。
    raw_text = _message_text(message)  # 取出返回文本。
    logger.info("preference.analysis.response_raw user_id=%s raw=%s", user_id, raw_text)  # 记录原始响应。
    parsed = _PREFERENCE_ANALYSIS_PARSER.parse(raw_text)  # 使用LangChain解析并映射到Pydantic模型。
    normalized = _normalize_llm_result(parsed)  # 标准化返回结果。
    axis_updates = _merge_confidence(normalized["axis_updates"], similarity_by_axis)  # 融合置信度。
    result = {  # 组装最终结果。
        "user_id": user_id,  # 用户 ID。
        "axis_updates": axis_updates,  # 轴更新列表。
        "avoid_patterns": normalized["avoid_patterns"],  # 避雷模式列表。
        "success_patterns": normalized["success_patterns"],  # 成功模式列表。
        "semantic_anchors": anchors,  # 召回锚点列表。
    }  # 结果对象结束。
    logger.info("preference.analysis.result user_id=%s result=%s", user_id, _safe_json_dumps(result))  # 记录最终结果。
    return result  # 返回分析结果。
