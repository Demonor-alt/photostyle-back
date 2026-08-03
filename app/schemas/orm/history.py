from datetime import datetime
from pydantic import Field

from app.schemas.base import BaseSchema


class PhotoStyleInputData(BaseSchema):  # 定义拍照建议输入数据模型，对应历史记录 input_data JSON 字段。
    time: str | None = None  # 用户选择或填写的拍照时间，可为空。
    style: str | None = None  # 用户选择的拍照风格，可为空。
    weather: str | None = None  # 用户选择或填写的天气信息，可为空。
    location: str | None = None  # 用户选择或填写的拍照地点，可为空。
    face_tags: list[str] = Field(default_factory=list)  # 人脸标签列表，允许元素结构暂时保持灵活。
    pose_tags: list[str] = Field(default_factory=list)  # 姿势标签列表，默认空列表。
    shot_tags: list[str] = Field(default_factory=list)  # 画幅/构图标签列表，默认空列表。
    extra_tags: list[str] = Field(default_factory=list)  # 前端附加选择项列表，默认空列表。


class PhotoStyleOutputData(BaseSchema):  # 定义拍照建议输出数据模型，对应历史记录 output_data JSON 字段。
    poses: list[str] = Field(default_factory=list)  # 姿势建议列表，默认空列表。
    makeup: list[str] = Field(default_factory=list)  # 妆容建议列表，默认空列表。
    outfit: list[str] = Field(default_factory=list)  # 穿搭建议列表，默认空列表。
    reason: str | None = None  # 建议原因，可为空。
    summary: str | None = None  # 整体总结，可为空。

class History(BaseSchema):
    id: int
    user_id: int
    input_data: PhotoStyleInputData = Field(default_factory=PhotoStyleInputData)
    output_data: PhotoStyleOutputData = Field(default_factory=PhotoStyleOutputData)
    makeup_rating: int = 0
    outfit_rating: int = 0
    pose_rating: int = 0
    feedback_comment: str | None = None
    reviewed: bool = False
    created_at: datetime | None = None