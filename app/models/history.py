from datetime import datetime  # 引入datetime用于时间戳
from typing import Optional  # 引入类型标注


class History:  # 定义历史记录ORM模型
    """历史记录数据库模型"""
    
    def __init__(
        self,
        id: int,
        user_id: int,
        input_data: dict,
        output_data: dict,
        liked: bool = False,
        shot_success: bool = False,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.id = id  # 历史记录ID
        self.user_id = user_id  # 用户ID
        self.input_data = input_data  # 输入数据
        self.output_data = output_data  # 输出数据
        self.liked = liked  # 用户是否喜欢
        self.shot_success = shot_success  # 是否出片成功
        self.created_at = created_at  # 创建时间
        self.updated_at = updated_at  # 更新时间
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "input_data": self.input_data,
            "output_data": self.output_data,
            "liked": self.liked,
            "shot_success": self.shot_success,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
