from typing import Any

from app.schemas.base import BaseSchema
from app.schemas.orm.user_persona import SemanticAxes
from pydantic import Field  # 引入Field用于默认工厂

# 更新用户画像参数
class UpsertUserPersonaRequest(BaseSchema):
    user_id: int
    semantic_axes: SemanticAxes = Field(default_factory=SemanticAxes)
