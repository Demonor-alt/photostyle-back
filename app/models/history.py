"""历史记录模型定义"""
from datetime import datetime
from sqlalchemy import Column, Integer, JSON, Boolean, DateTime, ForeignKey, Text
from app.db.database import Base


class PhotoStyleHistory(Base):
    """拍照风格历史记录表"""
    __tablename__ = "photo_style_history"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(Integer, ForeignKey("photo_style_users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    input_data = Column(JSON, nullable=False, comment="输入数据")
    output_data = Column(JSON, nullable=False, comment="输出数据")
    makeup_rating = Column(Integer, nullable=False, default=0, comment="妆容评分")
    outfit_rating = Column(Integer, nullable=False, default=0, comment="穿搭评分")
    pose_rating = Column(Integer, nullable=False, default=0, comment="姿势评分")
    feedback_comment = Column(Text, nullable=True, comment="点评内容")
    reviewed = Column(Boolean, nullable=False, default=False, comment="是否已点评")
    shot_success = Column(Boolean, nullable=False, default=False, comment="是否出片成功")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "makeup_rating": self.makeup_rating,
            "outfit_rating": self.outfit_rating,
            "pose_rating": self.pose_rating,
            "feedback_comment": self.feedback_comment,
            "reviewed": self.reviewed,
            "shot_success": self.shot_success,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
