from datetime import datetime
from typing import Any

from app.schemas.base import BaseSchema


class User(BaseSchema):
    id: int
    username: str
    password_hash: str
    photo_path: str | None = None
    photo_mime_type: str | None = None
    face_analysis: dict[str, Any] | None = None
    simple_analysis: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
