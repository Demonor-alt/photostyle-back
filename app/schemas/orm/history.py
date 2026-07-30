from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema


class History(BaseSchema):
    id: int
    user_id: int
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    makeup_rating: int = 0
    outfit_rating: int = 0
    pose_rating: int = 0
    feedback_comment: str | None = None
    reviewed: bool = False
    created_at: datetime | None = None
