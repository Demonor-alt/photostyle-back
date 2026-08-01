"""用户偏好分析服务。"""  # 模块说明：负责分析用户评论并生成偏好画像更新结果。
from app.db.user_persona_mapper import get_user_persona_by_id
from app.schemas.llm import PreferenceAnalysisOutput


from __future__ import annotations  # 启用前向引用类型注解。

import os  # 用于读取环境变量。
from typing import Any  # 用于表示任意类型。


from app.rag.semantic_anchor_milvus_service import search_similar_anchor  # 引入 Milvus 语义锚点检索方法。
from app.utils.runtime import logger  # 引入统一日志器。
from app.services.llm.qwen_user_persona_analysis_client import analyze_user_preference  # 引入用户偏好分析方法。
from app.rag.vector_writing import get_history_record_by_history_id  # 引入获取历史记录方法。
from app.config.constants import DEFAULT_ANCHOR_TOP_K # 引入默认召回语义锚点数量。


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


def user_preference( history_id: int
) -> dict[str, Any]:  # 返回结构化分析结果。
    """分析用户评论中的偏好变化，返回结构化结果但不写数据库。"""
    current_history = get_history_record_by_history_id(history_id)  # 获取历史记录信息
    user_id = current_history["user_id"]  # 获取历史记录用户ID
    user_persona = get_user_persona_by_id(user_id)  # 获取用户画像
    comment = current_history["feedback_comment"]  # 获取历史记录评论
    anchors = _search_semantic_anchors(comment, top_k=DEFAULT_ANCHOR_TOP_K)  # 检索语义锚点。
    similarity_by_axis = _best_similarity_by_axis(anchors)  # 计算每个轴的最佳相似度。
    normalized = analyze_user_preference()  # 分析用户偏好。
    axis_updates = _merge_confidence(normalized["axis_updates"], similarity_by_axis)  # 融合置信度。
    result = {  # 组装最终结果。
        "user_id": user_id,  # 用户 ID。
        "axis_updates": axis_updates,  # 轴更新列表。
        "avoid_patterns": normalized["avoid_patterns"],  # 避雷模式列表。
        "success_patterns": normalized["success_patterns"],  # 成功模式列表。
        "semantic_anchors": anchors,  # 召回锚点列表。
    }  # 结果对象结束。
    logger.info("preference.analysis.result user_id=%s result=%s", user_id, result)  # 记录最终结果。
    return result  # 返回分析结果。
