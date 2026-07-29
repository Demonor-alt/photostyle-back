from typing import List, Optional  # 引入类型标注用于描述字段结构

from pydantic import Field  # 引入Field用于定义字段默认值

from .base import BaseSchema  # 引入公共Schema基类


class SuggestRequest(BaseSchema):  # 定义拍照建议请求模型
    username: str  # 当前登录用户名
    style: str  # 用户选择的风格
    location: Optional[str] = None  # 拍照地点
    time: Optional[str] = None  # 拍照时间
    weather: Optional[str] = None  # 拍照天气
    face_tags: List[str] = Field(default_factory=list)  # 人脸标签，可多选
    shot_tags: List[str] = Field(default_factory=list)  # 构图标签，可多选
    pose_tags: List[str] = Field(default_factory=list)  # 姿势标签，可多选
    extra_tags: List[str] = Field(default_factory=list)  # 额外选择项，便于前端一次性上传全部选项
    image_path: Optional[str] = None  # 图片路径
    image_mime_type: Optional[str] = None  # 图片MIME类型
    face_analysis: Optional[dict] = None  # 可选的人脸分析结果，后端会优先从数据库获取


class SuggestResponse(BaseSchema):  # 定义拍照建议响应模型
    reason: Optional[str] = None  # 建议原因
    outfit: Optional[List[str]] = None  # 穿搭建议列表
    makeup: Optional[List[str]] = None  # 妆容建议列表
    poses: Optional[List[str]] = None  # 姿势建议列表
    summary: Optional[str] = None  # 整体总结


class DatabaseStatusResponse(BaseSchema):  # 定义数据库状态响应模型
    connected: bool  # 是否已连接
    message: str  # 状态信息
