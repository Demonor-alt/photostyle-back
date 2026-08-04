"""用户人格画像模型定义"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from app.db.database import Base
from app.db.models.user_model import UserModel


DEFAULT_SEMANTIC_AXES = {
    "color_saturation": 0,
    "accessory_level": 0,
    "makeup_intensity": 0,
    "pose_staged": 0,
    "body_openness": 0,
    "emotion_expression": 0,
    "lighting_strength": 0,
    "fashion_level": 0,
    "maturity": 0,
    "femininity": 0,
    "sweetness": 0,
    "retro": 0,
    "oriental": 0,
}


def default_semantic_axes() -> dict:
    """返回新的语义轴默认结构，避免多行记录共享同一个可变对象。"""
    return dict(DEFAULT_SEMANTIC_AXES)


class UserPersonaModel(Base):
    """用户人格画像表模型"""
    __tablename__ = "user_persona"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户人格画像ID")
    user_id = Column(
        BigInteger,
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="关联用户ID",
    )
    semantic_axes = Column(JSON, nullable=False, default=default_semantic_axes, comment="用户语义偏好轴")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    user = relationship(UserModel, back_populates="persona")
