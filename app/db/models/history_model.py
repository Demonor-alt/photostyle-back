"""历史记录模型定义"""
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, JSON, Boolean, DateTime, ForeignKey, Text
from app.db.database import Base


class HistoryModel(Base):
    """拍照风格历史记录表"""
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(Integer, ForeignKey("photo_style_users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    input_data = Column(JSON, nullable=False, comment="输入数据")
    output_data = Column(JSON, nullable=False, comment="输出数据")
    makeup_rating = Column(Integer, nullable=False, default=0, comment="妆容评分")
    outfit_rating = Column(Integer, nullable=False, default=0, comment="穿搭评分")
    pose_rating = Column(Integer, nullable=False, default=0, comment="姿势评分")
    feedback_comment = Column(Text, nullable=True, comment="点评内容")
    reviewed = Column(Boolean, nullable=False, default=False, comment="是否已点评")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None), comment="创建时间")
