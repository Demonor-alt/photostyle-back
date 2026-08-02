from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema


class UserPersona(BaseSchema):
    id: int
    user_id: int
    semantic_axes: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
