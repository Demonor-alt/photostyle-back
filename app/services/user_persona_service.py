"""用户偏好分析服务。"""  # 模块说明：负责分析用户评论并生成偏好画像更新结果。
from __future__ import annotations  # 启用前向引用类型注解。
from typing import Any  # 用于表示任意类型。

from app.schemas.dto.semantic_anchor_dto import (
    SearchSimilarAnchorResult,
    SearchSimilarAnchorResponse,
    SemanticAnchorAxisCandidate,
    SemanticAnchorAxisCandidates,
    SemanticAnchorEvidence,
)  # 引入语义锚点及语义轴候选 DTO。
from app.rag.semantic_anchor_milvus_service import search_similar_anchor  # 引入 Milvus 语义锚点检索方法。
from app.utils.runtime import logger  # 引入统一日志器。
from app.services.llm.qwen_user_persona_analysis_client import analyze_user_preference  # 引入用户偏好分析方法。
from app.schemas.llm import UserPersonaAnalysisRequest  # 引入用户偏好分析请求模型。
from app.rag.vector_writing import get_history_record_by_history_id  # 引入获取历史记录方法。
from app.db.history_mapper import list_history_records_by_user_id  # 引入按用户查询历史数量方法。
from app.db.user_persona_mapper import get_user_persona_by_id, update_user_persona_by_id  # 引入读取与更新用户历史画像方法。
from app.config.constants import (
    DEFAULT_ANCHOR_TOP_K,
    SEMANTIC_ANCHOR_MIN_COUNT,
    SEMANTIC_ANCHOR_SIMILARITY_THRESHOLD,
    SIMILARITY_MAX,
    SIMILARITY_MIN,
    AXIS_VALUE_MIN,
    OLD_USER_PERSONA_UPDATE_MIN,
    OLD_USER_PERSONA_UPDATE_MAX,
    MILVUS_USER_PERSONA_UPDATE_MAX
)
from app.utils.semantic_anchors import clamp, load_semantic_axes_config
from app.schemas.orm.history import History  # 引入历史记录模型。

_SCORE_FIELDS = ("makeup_rating", "outfit_rating", "pose_rating")  # 定义可影响语义轴更新幅度的评分字段。


def _search_semantic_anchors(comment: str, top_k: int) -> SearchSimilarAnchorResponse:  # 根据评论检索语义锚点。
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
    return SearchSimilarAnchorResponse(anchors=normalized)  # 返回标准化锚点列表。


def _best_similarity_by_axis(payload: SearchSimilarAnchorResponse) -> SemanticAnchorAxisCandidates:  # 按语义轴聚合召回锚点。
    """按轴聚合高质量锚点，返回语义轴候选 DTO。"""
    grouped: dict[str, list[SemanticAnchorEvidence]] = {}
    for anchor in payload.anchors:  # 遍历 Milvus 召回的每个语义锚点。
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


def _load_semantic_axis_effect_fields() -> dict[str, str]:  # 读取每个语义轴受哪个评分字段影响。
    semantic_axes_config = load_semantic_axes_config()  # 复用工具方法读取 semantic_axes.yaml 配置。
    effect_fields: dict[str, str] = {}  # 初始化轴名到影响字段的映射。
    for axis_name, axis_config in semantic_axes_config.items():  # 遍历每个语义轴配置项。
        effect_field = str(axis_config.get("effect_field") or "").strip()  # 获取并清理影响评分字段。
        if effect_field:  # 如果影响字段有效。
            effect_fields[axis_name] = effect_field  # 保存该语义轴对应的影响字段。
    return effect_fields  # 返回语义轴影响字段映射。


def _rating_update_weight(history: History, effect_field: str) -> float:  # 根据评分计算本次新画像更新权重。
    scores = [float(getattr(history, field, 0) or 0) for field in _SCORE_FIELDS] if effect_field == "all" else [float(getattr(history, effect_field, 0) or 0)]  # 获取影响该语义轴的评分列表。
    score = max(scores) if scores else 0.0  # all 取最高分，单字段取对应分，分数越高更新越大。
    return clamp(score / 10.0, 0.0, 1.0) * 0.4  # 将评分归一化为最多 0.4 的新画像权重。


def _old_persona_weight(history_count: int) -> float:  # 根据用户历史数量计算旧画像权重。
    return clamp(OLD_USER_PERSONA_UPDATE_MIN + min(max(history_count, 0), 20) / 100.0, OLD_USER_PERSONA_UPDATE_MIN, OLD_USER_PERSONA_UPDATE_MAX)  # 历史越多旧画像占比越大，且始终大于等于 OLD_USER_PERSONA_UPDATE_MIN。


def _merge_semantic_axes(  # 融合旧画像、LLM 输出和 Milvus 候选值。
    *,  # 强制调用方使用关键字参数，提升可读性。
    old_axes: dict[str, Any],  # 旧画像中的语义轴字典。
    llm_axis_updates: list[Any],  # LLM 本次输出的语义轴更新列表，元素通常是 Pydantic 模型。
    anchor_stats_by_axis: dict[str, SemanticAnchorAxisCandidate],  # Milvus 按语义轴聚合后的候选结果。
    axis_effect_fields: dict[str, str],  # semantic_axes.yaml 中的轴影响字段映射。
    current_history: Any,  # 当前历史记录，提供评分数据。
    history_count: int,  # 当前用户历史记录数量。
) -> dict[str, float]:  # 返回可直接入库的轴名和值字典。
    llm_values = {item.axis_name: float(item.value) for item in llm_axis_updates if item.axis_name}  # 将 LLM 更新列表转为轴名到值的映射。
    old_weight = _old_persona_weight(history_count)  # 根据历史数量计算旧画像权重。
    semantic_axes: dict[str, float] = {}  # 初始化最终入库语义轴字典。
    for axis_name, effect_field in axis_effect_fields.items():  # 遍历配置文件中的全部语义轴。
        old_value = float(old_axes.get(axis_name, 0.0) or 0.0)  # 获取旧画像中该轴的原值，缺失则为 0。
        llm_value = llm_values.get(axis_name, old_value)  # 获取 LLM 新值，缺失则沿用旧值。
        anchor_stats = anchor_stats_by_axis.get(axis_name)  # 获取该轴的 Milvus 候选统计。
        milvus_similarity = clamp(anchor_stats.confidence if anchor_stats else SIMILARITY_MIN, SIMILARITY_MIN, SIMILARITY_MAX)  # 获取并限制 Milvus 置信度。
        milvus_weight = min(milvus_similarity * 0.1, MILVUS_USER_PERSONA_UPDATE_MAX)  # Milvus 对最终结果最多只占 MILVUS_USER_PERSONA_UPDATE_MAX。
        new_weight = _rating_update_weight(current_history, effect_field)  # 根据 effect_field 对应评分计算本次更新权重。
        remaining_weight = max(0.0, 1.0 - old_weight - milvus_weight)  # 计算除旧画像和 Milvus 之外的剩余权重。
        llm_weight = min(new_weight, remaining_weight)  # LLM 本次更新权重不超过评分允许值和剩余空间。
        normalized_old_weight = 1.0 - llm_weight - milvus_weight  # 将未使用权重都留给旧画像，确保旧画像占比足够大。
        milvus_value = float(anchor_stats.value) if anchor_stats else old_value  # 获取 Milvus 候选轴值，缺失则使用旧值避免扰动。
        merged_value = normalized_old_weight * old_value + llm_weight * llm_value + milvus_weight * milvus_value  # 按权重融合最终轴值。
        semantic_axes[axis_name] = round(clamp(merged_value, AXIS_VALUE_MIN, 1.0), 4)  # 限制最终轴值范围并保存。
    return semantic_axes  # 返回最终 semantic_axes 入库字典。

def user_persona_semantic_axes( history_id: int
) -> dict[str, Any]:  # 返回结构化分析结果。
    current_history = get_history_record_by_history_id(history_id)  # 获取历史记录信息
    comment = current_history.feedback_comment or ""  # 获取历史记录评论。
    anchors = _search_semantic_anchors(comment, top_k=DEFAULT_ANCHOR_TOP_K)  # 检索语义锚点。
    anchor_axis_candidates = _best_similarity_by_axis(anchors)  # 计算每个轴的聚合候选结果。

    anchor_stats_by_axis = {candidate.axis_name: candidate for candidate in anchor_axis_candidates.axis_candidates}
    user_id = int(current_history.user_id)  # 获取当前用户 ID。
    current_persona = get_user_persona_by_id(user_id)
    input_data = current_history.input_data.model_dump(mode="json", by_alias=True)
    output_data = current_history.output_data.model_dump(mode="json", by_alias=True)
    old_semantic_axes = current_persona.semantic_axes.root if current_persona else None
    payload = UserPersonaAnalysisRequest(
        input_data=input_data,
        output_data=output_data,
        comment=comment,
        makeup_rating=current_history.makeup_rating or 0,
        outfit_rating=current_history.outfit_rating or 0,
        pose_rating=current_history.pose_rating or 0,
        old_semantic_axes=old_semantic_axes,
        anchors=anchor_axis_candidates,
    )
    normalized = analyze_user_preference(payload)  # 分析用户偏好。
    axis_effect_fields = _load_semantic_axis_effect_fields()  # 读取语义轴与评分影响字段配置。
    current_semantic_axes = current_persona.semantic_axes.root if current_persona else {}  # 获取旧画像语义轴，用户无画像时使用空字典。
    history_count = len(list_history_records_by_user_id(user_id))  # 查询用户历史数量，历史越多旧画像占比越大。
    semantic_axes = _merge_semantic_axes(  # 融合旧画像、LLM 本次结果和 Milvus 候选结果。
        old_axes=current_semantic_axes,  # 传入旧画像轴名和值。
        llm_axis_updates=normalized.axis_updates,  # 传入 LLM 本次分析出的语义轴更新。
        anchor_stats_by_axis=anchor_stats_by_axis,  # 传入 Milvus 聚合候选结果。
        axis_effect_fields=axis_effect_fields,  # 传入配置文件中每个轴受哪个评分字段影响。
        current_history=current_history,  # 传入当前历史记录评分。
        history_count=history_count,  # 传入用户历史数量。
    )  # 得到可直接入库的 semantic_axes 字典。
    normalized.axis_updates = [item.model_copy(update={"value": semantic_axes[item.axis_name]}) for item in normalized.axis_updates if item.axis_name in semantic_axes]  # 同步 Pydantic 分析结果中的最终融合值。
    update_user_persona_by_id(  # 更新或创建用户画像数据库记录。
        user_id=user_id,  # 指定要更新的用户 ID。
        semantic_axes=semantic_axes,  # 写入轴名和值组成的最新语义轴画像。
    )  # 获取更新后的用户画像。
    result = {  # 组装最终结果。
        "user_id": user_id,  # 用户 ID。
        "semantic_axes": semantic_axes,  # 直接返回轴名和值组成的语义轴画像。
        "semantic_anchors": anchors,  # 召回锚点列表。
        "semantic_anchor_axis_candidates": anchor_axis_candidates,
    }  # 结果对象结束。
    logger.info("preference.analysis.result user_id=%s result=%s", user_id, result)  # 记录最终结果。
    return result  # 返回分析结果。