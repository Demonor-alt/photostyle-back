"""ORM 模型包"""
from app.db.models.user import User
from app.db.models.history import PhotoStyleHistory
from app.db.models.user_persona import UserPersona

# 统一导出所有 ORM 模型，确保初始化数据库表结构时能注册用户人格画像表
__all__ = ["User", "PhotoStyleHistory", "UserPersona"]
