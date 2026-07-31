from typing import Optional  # 引入类型标注用于描述字段结构

from app.schemas.base import BaseSchema  # 引入公共Schema基类


class HistoryUserRecord(BaseSchema):  # 定义保存历史记录请求模型
    user_id: int  # 用户ID
    input_data: dict  # 输入数据
    output_data: dict  # 输出数据
    makeup_rating: int = 0  # 妆容评分
    outfit_rating: int = 0  # 穿搭评分
    pose_rating: int = 0  # 姿势评分
    feedback_comment: Optional[str] = None  # 点评内容
    reviewed: bool = False  # 是否已点评
