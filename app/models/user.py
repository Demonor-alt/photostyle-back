"""用户模型定义"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, Text, JSON, DateTime
from app.db.database import Base


class User(Base):
    """用户表模型"""
    __tablename__ = "photo_style_users"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(64), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    photo_path = Column(String(500), nullable=True, comment="用户照片路径")
    photo_mime_type = Column(String(100), nullable=True, comment="照片MIME类型")
    face_analysis = Column(JSON, nullable=True, comment="人脸分析数据")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "username": self.username,
            "password_hash": self.password_hash,
            "photo_path": self.photo_path,
            "photo_mime_type": self.photo_mime_type,
            "face_analysis": self.face_analysis,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
