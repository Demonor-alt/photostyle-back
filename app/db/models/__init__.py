"""ORM 模型包"""
from app.db.models.user_model import UserModel
from app.db.models.history_model import HistoryModel
from app.db.models.user_persona_model import UserPersonaModel

# 统一导出所有 ORM 模型，确保初始化数据库表结构时能注册用户人格画像表
__all__ = ["UserModel", "HistoryModel", "UserPersonaModel"]
