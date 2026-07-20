"""历史记录模型定义"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, JSON, Boolean, DateTime, ForeignKey
from app.db.database import Base


class PhotoStyleHistory(Base):
    """拍照风格历史记录表"""
    __tablename__ = "photo_style_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    user_id = Column(BigInteger, ForeignKey("photo_style_users.id", ondelete="CASCADE"), nullable=False, index=True, comment="用户ID")
    input_data = Column(JSON, nullable=False, comment="输入数据")
    output_data = Column(JSON, nullable=False, comment="输出数据")
    liked = Column(Boolean, nullable=False, default=False, comment="是否喜欢")
    shot_success = Column(Boolean, nullable=False, default=False, comment="是否出片成功")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "liked": self.liked,
            "shot_success": self.shot_success,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
