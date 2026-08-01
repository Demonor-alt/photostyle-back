from typing import Any

from pydantic import Field

from app.schemas.base import BaseSchema


# 检索语义锚点请求
class SearchSimilarAnchorRequest(BaseSchema):
    """语义锚点相似检索参数。"""
    query_text: str = Field(description="查询文本")
    top_k: int = Field(default=5, ge=1, description="返回数量上限")
    min_score: float | None = Field(default=None, description="可选最小相似度分数")
    filters: dict[str, Any] | None = Field(default=None, description="可选过滤条件，如 axis_name、category")


# 检索语义锚点返回
class SearchSimilarAnchorResult(BaseSchema):
    """语义锚点相似检索返回项。"""
    id: int | None = Field(default=None, description="Milvus 实体 ID")
    axis_name: str | None = Field(default=None, description="语义轴名称")
    text: str | None = Field(default=None, description="语义锚点文本")
    axis_value: float | None = Field(default=None, description="语义轴取值")
    category: str | None = Field(default=None, description="锚点类别")
    score: float = Field(description="相似度分数")
class SearchSimilarAnchorResponse(BaseSchema):
    """语义锚点相似检索返回。"""
    anchors: list[SearchSimilarAnchorResult] = Field(description="语义锚点列表")
