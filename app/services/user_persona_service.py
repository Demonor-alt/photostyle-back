"""用户偏好分析服务。"""  # 模块说明：负责分析用户评论并生成偏好画像更新结果。
from __future__ import annotations  # 启用前向引用类型注解。
from typing import Any  # 用于表示任意类型。

from app.schemas.dto.semantic_anchor_dto import (
    SearchSimilarAnchorResult,
    SemanticAnchorAxisCandidate,
    SemanticAnchorAxisCandidates,
    SemanticAnchorEvidence,
)  # 引入语义锚点及语义轴候选 DTO。
from app.rag.semantic_anchor_milvus_service import search_similar_anchor  # 引入 Milvus 语义锚点检索方法。
from app.utils.runtime import logger  # 引入统一日志器。
from app.services.llm.qwen_user_persona_analysis_client import analyze_user_preference  # 引入用户偏好分析方法。
from app.schemas.llm import UserPersonaAnalysisRequest  # 引入用户偏好分析请求模型。
from app.rag.vector_writing import get_history_record_by_history_id  # 引入获取历史记录方法。
from app.db.user_persona_mapper import get_user_persona_by_id  # 引入读取用户历史画像方法。
from app.config.constants import (
    DEFAULT_ANCHOR_TOP_K,
    SEMANTIC_ANCHOR_MIN_COUNT,
    SEMANTIC_ANCHOR_SIMILARITY_THRESHOLD,
    SIMILARITY_MAX,
    SIMILARITY_MIN,
)
from app.utils.semantic_anchors import clamp


def _search_semantic_anchors(comment: str, top_k: int) -> list[SearchSimilarAnchorResult]:  # 根据评论检索语义锚点。
    """使用评论文本向量检索全局 Semantic Anchor Library。"""  # 说明调用向量检索。
    anchors = search_similar_anchor(query_text=comment, top_k=top_k)  # 执行相似锚点搜索。
    normalized: list[SearchSimilarAnchorResult] = []  # 初始化标准化锚点列表。
    for anchor in anchors:  # 遍历召回锚点。
        normalized.append(
            SearchSimilarAnchorResult(
                id=anchor.id,
                axis_name=anchor.axis_name,
                text=anchor.text,
                axis_value=anchor.axis_value,
                category=anchor.category,
                similarity=clamp(anchor.similarity, min_value=SIMILARITY_MIN, max_value=SIMILARITY_MAX),
            )
        )
    logger.info("preference.semantic_anchors.recalled count=%s", len(normalized))  # 记录召回数量。
    return normalized  # 返回标准化锚点列表。


def _best_similarity_by_axis(anchors: list[SearchSimilarAnchorResult]) -> SemanticAnchorAxisCandidates:  # 按语义轴聚合召回锚点。
    """按轴聚合高质量锚点，返回语义轴候选 DTO。"""
    grouped: dict[str, list[SemanticAnchorEvidence]] = {}
    for anchor in anchors:  # 遍历 Milvus 召回的每个语义锚点。
        axis_name = str(anchor.axis_name or "").strip()  # 读取锚点所属语义轴，并去掉首尾空白。
        if not axis_name:  # 如果锚点没有有效语义轴名称。
            continue  # 跳过无语义轴名称的锚点。
        similarity = clamp(anchor.similarity, SIMILARITY_MIN, SIMILARITY_MAX)  # 将锚点相似度限制在合法范围内。
        if anchor.axis_value is None or similarity < SEMANTIC_ANCHOR_SIMILARITY_THRESHOLD:  # 如果缺少轴值或相似度低于阈值。
            continue  # 跳过低质量或不完整的锚点。
        grouped.setdefault(axis_name, []).append(
            SemanticAnchorEvidence(
                text=anchor.text,
                axis_value=float(anchor.axis_value),
                similarity=round(similarity, 4),
            )
        )  # 将原始证据加入对应语义轴分组。

    axis_candidates: list[SemanticAnchorAxisCandidate] = []  # 初始化最终聚合结果。
    for axis_name, evidence in grouped.items():  # 遍历每个语义轴及其召回到的有效锚点。
        if len(evidence) < SEMANTIC_ANCHOR_MIN_COUNT:  # 如果该语义轴有效锚点数量不足。
            continue  # 跳过样本数不足的语义轴，避免噪声。
        similarity_sum = sum(item.similarity for item in evidence)  # 计算该语义轴下所有有效锚点的相似度总和。
        axis_candidates.append(
            SemanticAnchorAxisCandidate(
                axis_name=axis_name,
                value=round(sum(item.axis_value * item.similarity for item in evidence) / similarity_sum, 4),
                confidence=round(max(item.similarity for item in evidence), 4),
                support_count=len(evidence),
                similarity_sum=round(similarity_sum, 4),
                evidence=evidence,
            )
        )
    axis_candidates.sort(key=lambda item: (item.confidence, item.similarity_sum), reverse=True)
    return SemanticAnchorAxisCandidates(axis_candidates=axis_candidates)  # 返回按语义轴聚合后的候选 DTO。


def user_preference( history_id: int
) -> dict[str, Any]:  # 返回结构化分析结果。
    """分析用户评论中的偏好变化，返回结构化结果但不写数据库。"""
    current_history = get_history_record_by_history_id(history_id)  # 获取历史记录信息
    comment = current_history.get("feedback_comment") # 获取历史记录评论
    anchors = _search_semantic_anchors(comment, top_k=DEFAULT_ANCHOR_TOP_K)  # 检索语义锚点。
    anchor_axis_candidates = _best_similarity_by_axis(anchors)  # 计算每个轴的聚合候选结果。

    anchor_stats_by_axis = {candidate.axis_name: candidate for candidate in anchor_axis_candidates.axis_candidates}
    current_persona = get_user_persona_by_id(int(current_history.get("user_id")))
    payload = UserPersonaAnalysisRequest(
        input_data=current_history.get("input_data") or {},
        output_data=current_history.get("output_data") or {},
        comment=comment,
        makeup_rating=current_history.get("makeup_rating") or 0,
        outfit_rating=current_history.get("outfit_rating") or 0,
        pose_rating=current_history.get("pose_rating") or 0,
        old_semantic_axes=current_persona.semantic_axes if current_persona else None,
        anchors=anchor_axis_candidates,
    )
    normalized = analyze_user_preference(payload)  # 分析用户偏好。
    axis_updates: list[dict[str, Any]] = []  # 初始化融合后的轴更新列表。
    for update in normalized["axis_updates"]:  # 遍历 LLM 输出的轴更新。
        axis_name = update["axis_name"]  # 获取语义轴名称。
        llm_confidence = clamp(update["value"])  # 标准化 LLM 置信度。
        anchor_stats = anchor_stats_by_axis.get(axis_name)
        milvus_similarity = clamp(anchor_stats.confidence if anchor_stats else 0.0, 0.0, 1.0)  # 标准化 Milvus 相似度。
        axis_updates.append(  # 追加融合后的轴更新。
            {
                "axis_name": axis_name,
                "value": update["value"],
                "confidence": round(llm_confidence * 0.6 + milvus_similarity * 0.4, 4),
                "reason": update["reason"],
                "llm_confidence": llm_confidence,
                "milvus_similarity": milvus_similarity,
                "milvus_axis_value": anchor_stats.value if anchor_stats else None,
            }
        )
    result = {  # 组装最终结果。
        "user_id": current_history.get("user_id"),  # 用户 ID。
        "axis_updates": axis_updates,  # 轴更新列表。
        "avoid_patterns": normalized["avoid_patterns"],  # 避雷模式列表。
        "success_patterns": normalized["success_patterns"],  # 成功模式列表。
        "semantic_anchors": anchors,  # 召回锚点列表。
        "semantic_anchor_axis_candidates": anchor_axis_candidates,
    }  # 结果对象结束。
    logger.info("preference.analysis.result user_id=%s result=%s", current_history.get("user_id"), result)  # 记录最终结果。
    return result  # 返回分析结果。
