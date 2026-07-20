from datetime import datetime  # 引入datetime用于时间戳
from typing import Optional  # 引入类型标注


class User:  # 定义用户ORM模型
    """用户数据库模型"""
    
    def __init__(
        self,
        id: int,
        username: str,
        password: str,
        photo_path: Optional[str] = None,
        photo_mime_type: Optional[str] = None,
        face_analysis: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id  # 用户ID
        self.username = username  # 用户名
        self.password = password  # 密码（已加密）
        self.photo_path = photo_path  # 图片路径
        self.photo_mime_type = photo_mime_type  # 图片类型
        self.face_analysis = face_analysis  # 人脸分析结果
        self.created_at = created_at  # 创建时间
        self.updated_at = updated_at  # 更新时间
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "username": self.username,
            "password": self.password,
            "photo_path": self.photo_path,
            "photo_mime_type": self.photo_mime_type,
            "face_analysis": self.face_analysis,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
