"""已处理事件模型定义。"""
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, String

from app.db.database import Base


class ProcessedEvent(Base):
    """消费者幂等事件表，用于避免同一 event_id 被重复处理。"""
    __tablename__ = "processed_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True, comment="记录ID")
    event_id = Column(String(128), unique=True, nullable=False, index=True, comment="业务事件ID")
    event_type = Column(String(128), nullable=False, comment="事件类型")
    consumer = Column(String(128), nullable=False, comment="消费者名称")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, comment="处理完成时间")

    def to_dict(self) -> dict:
        """转换为字典，便于日志记录。"""
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "consumer": self.consumer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
