from typing import Any

from app.schemas.base import BaseSchema
from app.schemas.orm.user_persona import SemanticAxes


# 更新用户画像参数
class UpsertUserPersonaRequest(BaseSchema):
    user_id: int
    semantic_axes: SemanticAxes | dict[str, Any]
