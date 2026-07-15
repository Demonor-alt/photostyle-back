from datetime import datetime  # 引入datetime用于描述时间字段
from typing import List, Optional  # 引入类型标注用于描述字段结构

from pydantic import BaseModel, Field  # 引入Pydantic用于定义请求响应模型


class SuggestRequest(BaseModel):  # 定义拍照建议请求模型
    username: str  # 当前登录用户名
    style: str  # 用户选择的风格
    location: Optional[str] = None  # 拍照地点
    time: Optional[str] = None  # 拍照时间
    weather: Optional[str] = None  # 拍照天气
    face_tags: List[str] = Field(default_factory=list)  # 人脸标签，可多选
    shot_tags: List[str] = Field(default_factory=list)  # 构图标签，可多选
    pose_tags: List[str] = Field(default_factory=list)  # 姿势标签，可多选
    extra_tags: List[str] = Field(default_factory=list)  # 额外选择项，便于前端一次性上传全部选项
    face_analysis: Optional[dict] = None  # 可选的人脸分析结果，后端会优先从数据库获取


class SuggestResponse(BaseModel):  # 定义拍照建议响应模型
    outfit: List[str]  # 穿搭建议列表
    makeup: List[str]  # 妆容建议列表
    poses: List[str]  # 姿势建议列表
    summary: str  # 整体总结


class HistoryRecord(BaseModel):  # 定义历史记录模型
    user_id: int  # 用户ID
    input_data: dict  # 输入数据（不再绑定SuggestRequest）
    output_data: SuggestResponse  # 输出数据
    liked: bool = False  # 用户是否喜欢
    shot_success: bool = False  # 是否出片成功


class FeedbackRequest(BaseModel):  # 定义用户反馈请求模型
    history_id: Optional[int] = None  # 历史记录ID
    liked: bool = False  # 用户是否喜欢
    shot_success: bool = False  # 是否出片成功
    comment: Optional[str] = None  # 用户补充评论


class LoginRequest(BaseModel):  # 定义登录请求模型
    username: str  # 用户名
    password: str  # 密码


class RegisterRequest(BaseModel):  # 定义注册请求模型
    username: str  # 用户名
    password: Optional[str] = None  # 密码，可选，未传时使用默认密码


class UpdateUserProfileRequest(BaseModel):  # 定义更新用户资料请求模型
    new_username: Optional[str] = None  # 新用户名
    password: Optional[str] = None  # 新密码
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果


class UserResponse(BaseModel):  # 定义用户响应模型
    id: int  # 用户ID
    username: str  # 用户名
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果
    created_at: Optional[datetime] = None  # 创建时间
    updated_at: Optional[datetime] = None  # 更新时间
