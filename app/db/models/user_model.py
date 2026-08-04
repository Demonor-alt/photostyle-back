"""用户模型定义"""
from datetime import datetime
from sqlalchemy import Column, BigInteger, String, JSON, DateTime
from sqlalchemy.orm import relationship
from app.db.database import Base


class UserModel(Base):
    """用户表模型"""
    __tablename__ = "user"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="用户ID")
    username = Column(String(64), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    photo_path = Column(String(500), nullable=True, comment="用户照片路径")
    photo_mime_type = Column(String(100), nullable=True, comment="照片MIME类型")
    face_analysis = Column(JSON, nullable=True, comment="人脸分析数据")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    persona = relationship(
        "UserPersonaModel",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
