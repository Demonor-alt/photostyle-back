import os  # 引入os用于读取环境变量
from sqlalchemy import text  # 引入text用于执行原生SQL
from app.db.models.history import PhotoStyleHistory  # 引入历史模型
from app.db.database import SessionLocal, engine  # 引入数据库会话和引擎
from app.schemas.orm.history import History


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
            "database_url": db_url.split("@")[-1] if "@" in db_url else db_url,
        }
    except Exception as e:
        raise ConnectionError(f"数据库连接失败：{str(e)}")


def _ensure_review_payload(record: dict) -> dict:
    return {
        "makeup_rating": int(record.get("makeup_rating", 0) or 0),
        "outfit_rating": int(record.get("outfit_rating", 0) or 0),
        "pose_rating": int(record.get("pose_rating", 0) or 0),
        "feedback_comment": record.get("feedback_comment") or None,
        "reviewed": bool(record.get("reviewed", False)),
    }


def save_history_record(record: dict) -> History:
    """保存历史记录并返回新增记录"""
    db = SessionLocal()
    try:
        review_payload = _ensure_review_payload(record)
        history = PhotoStyleHistory(
            user_id=record["user_id"],
            input_data=record["input_data"],
            output_data=record["output_data"],
            **review_payload,
        )
        db.add(history)
        db.commit()
        db.refresh(history)
        return History.model_validate(history)
    finally:
        db.close()


def update_history_feedback(history_id: int, makeup_rating: int, outfit_rating: int, pose_rating: int, feedback_comment: str | None) -> History:
    """更新历史记录反馈并返回最新记录"""
    db = SessionLocal()  # 创建数据库会话
    try:  # 开始事务
        history = db.query(PhotoStyleHistory).filter(PhotoStyleHistory.id == history_id).first()  # 查找历史记录
        if not history:  # 如果没有找到
            raise ValueError("历史记录不存在")  # 直接抛出异常

        history.makeup_rating = makeup_rating  # 更新妆容评分
        history.outfit_rating = outfit_rating  # 更新穿搭评分
        history.pose_rating = pose_rating  # 更新姿势评分
        history.feedback_comment = feedback_comment  # 更新点评内容
        history.reviewed = True  # 标记为已点评
        db.commit()  # 提交事务
        db.refresh(history)  # 刷新对象
        return History.model_validate(history)  # 返回Schema
    finally:  # 无论如何都关闭会话
        db.close()  # 关闭数据库会话


def get_history_record(history_id: int) -> History:
    """根据ID获取历史记录"""
    db = SessionLocal()  # 创建数据库会话
    try:  # 开始查询
        history = db.query(PhotoStyleHistory).filter(PhotoStyleHistory.id == history_id).first()  # 查找历史记录
        if not history:  # 如果没找到
            raise ValueError("历史记录不存在")  # 直接报错
        return History.model_validate(history)  # 返回Schema
    finally:  # 无论如何都关闭会话
        db.close()  # 关闭数据库会话


def list_history_records(user_id: int | None = None) -> list[History]:
    """查询历史记录，支持按用户ID筛选"""
    db = SessionLocal()
    try:
        query = db.query(PhotoStyleHistory)
        if user_id is not None:
            query = query.filter(PhotoStyleHistory.user_id == user_id)

        records = query.order_by(PhotoStyleHistory.id.desc()).all()
        return [History.model_validate(record) for record in records]
    finally:
        db.close()
