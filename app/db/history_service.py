import os
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.models.history import PhotoStyleHistory
from app.db.database import SessionLocal, engine


def get_database_status() -> dict:
    """获取数据库连接状态"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        db_url = os.getenv("DATABASE_URL", "")
        if "postgresql" in db_url:
            db_type = "PostgreSQL"
        elif "mysql" in db_url:
            db_type = "MySQL"
        else:
            db_type = "Unknown"
        
        return {
            "enabled": True,
            "database_type": db_type,
            "database_url": db_url.split("@")[-1] if "@" in db_url else db_url
        }
    except Exception as e:
        raise ConnectionError(f"数据库连接失败：{str(e)}")


def save_history_record(record: dict) -> None:
    """保存历史记录"""
    db = SessionLocal()
    try:
        history = PhotoStyleHistory(
            user_id=record["user_id"],
            input_data=record["input_data"],
            output_data=record["output_data"],
            liked=record.get("liked", False),
            shot_success=record.get("shot_success", False)
        )
        db.add(history)
        db.commit()
    finally:
        db.close()


def update_history_feedback(history_id: int, liked: bool, shot_success: bool) -> None:
    """更新历史记录反馈"""
    db = SessionLocal()
    try:
        history = db.query(PhotoStyleHistory).filter(PhotoStyleHistory.id == history_id).first()
        if not history:
            raise ValueError("历史记录不存在")
        
        history.liked = liked
        history.shot_success = shot_success
        db.commit()
    finally:
        db.close()


def list_history_records(user_id: int | None = None) -> list:
    """查询历史记录，支持按用户ID筛选"""
    db = SessionLocal()
    try:
        query = db.query(PhotoStyleHistory)
        if user_id is not None:
            query = query.filter(PhotoStyleHistory.user_id == user_id)
        
        records = query.order_by(PhotoStyleHistory.id.desc()).all()
        return [record.to_dict() for record in records]
    finally:
        db.close()
