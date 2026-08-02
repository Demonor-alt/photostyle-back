from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


# 检索语义锚点请求
class SearchSimilarAnchorRequest(BaseSchema):
    """语义锚点相似检索参数。"""
    query_text: str = Field(description="查询文本")
    top_k: int = Field(default=5, ge=1, description="返回数量上限")
    min_similarity: float | None = Field(default=None, description="可选最小相似度分数")
    filters: dict[str, Any] | None = Field(default=None, description="可选过滤条件，如 axis_name、category")


# 检索语义锚点返回
class SearchSimilarAnchorResult(BaseSchema):
    """语义锚点相似检索返回项。"""
    id: int | None = Field(default=None, description="Milvus 实体 ID")
    axis_name: str | None = Field(default=None, description="语义轴名称")
    text: str | None = Field(default=None, description="语义锚点文本")
    axis_value: float | None = Field(default=None, description="语义轴取值")
    category: str | None = Field(default=None, description="锚点类别")
    similarity: float = Field(description="相似度")
class SearchSimilarAnchorResponse(BaseSchema):
    """语义锚点相似检索返回。"""
    anchors: list[SearchSimilarAnchorResult] = Field(description="语义锚点列表")


# 给llm的语义轴集合
class SemanticAnchorEvidence(BaseSchema):
    """支撑语义轴判断的原始证据。"""
    text: str | None = Field(default=None, description="语义锚点文本")
    axis_value: float = Field(description="单条语义锚点在该语义轴上的取值")
    similarity: float = Field(description="单条语义锚点的匹配分数")
class SemanticAnchorAxisCandidate(BaseSchema):
    """单个语义轴的候选聚合结果。"""
    axis_name: str = Field(description="语义轴名称")
    value: float = Field(description="聚合后的用户当前意图估计")
    confidence: float = Field(description="该语义轴判断的可靠程度，取该轴最高匹配分数")
    support_count: int = Field(description="支持该语义轴判断的锚点数量")
    similarity_sum: float = Field(description="该语义轴所有匹配分数总和")
    evidence: list[SemanticAnchorEvidence] = Field(description="支撑该语义轴判断的原始证据")
class SemanticAnchorAxisCandidates(BaseSchema):
    """按语义轴聚合后的候选结果。"""
    axis_candidates: list[SemanticAnchorAxisCandidate] = Field(description="语义轴候选列表")



