from typing import List, Optional  # 引入类型标注用于描述字段结构

from fastapi import File, Form, UploadFile  # 引入FastAPI表单和文件处理
from pydantic import Field  # 引入Field用于定义字段默认值
from typing_extensions import Annotated  # 引入Annotated用于类型标注

from .base import BaseSchema  # 引入公共Schema基类


class SuggestFormParams:  # 定义建议生成表单参数（用于FastAPI依赖注入）
    def __init__(
        self,
        username: Annotated[str, Form(description="用户名")],
        style: Annotated[str, Form(description="风格")],
        location: Annotated[str | None, Form(description="地点")] = None,
        time: Annotated[str | None, Form(description="时间")] = None,
        weather: Annotated[str | None, Form(description="天气")] = None,
        face_tags: Annotated[str, Form(description="人脸标签JSON字符串")] = "[]",
        shot_tags: Annotated[str, Form(description="画幅标签JSON字符串")] = "[]",
        pose_tags: Annotated[str, Form(description="姿势标签JSON字符串")] = "[]",
        extra_tags: Annotated[str, Form(description="前端全部选择项")] = "[]",
        image: Annotated[UploadFile | None, File(description="上传图片文件")] = None,
    ):
        self.username = username
        self.style = style
        self.location = location
        self.time = time
        self.weather = weather
        self.face_tags = face_tags
        self.shot_tags = shot_tags
        self.pose_tags = pose_tags
        self.extra_tags = extra_tags
        self.image = image


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


class HistoryRecord(BaseSchema):  # 定义历史记录模型
    id: Optional[int] = None  # 历史记录ID
    user_id: int  # 用户ID
    input_data: dict  # 输入数据（不再绑定SuggestRequest）
    output_data: dict  # 输出数据（支持旧格式和新格式）
    makeup_rating: int = 0  # 妆容评分
    outfit_rating: int = 0  # 穿搭评分
    pose_rating: int = 0  # 姿势评分
    feedback_comment: Optional[str] = None  # 点评内容
    reviewed: bool = False  # 是否已点评
    created_at: Optional[str] = None  # 创建时间


class DatabaseStatusResponse(BaseSchema):  # 定义数据库状态响应模型
    connected: bool  # 是否已连接
    message: str  # 状态信息


class HistoryListResponse(BaseSchema):  # 定义历史记录列表响应模型
    items: List[HistoryRecord]  # 历史记录列表


class MessageResponse(BaseSchema):  # 定义通用消息响应模型
    message: str  # 消息内容


class SuggestApiData(BaseSchema):  # /suggest 接口业务数据
    suggestions: Optional[str] = None
    outfit: Optional[List[str]] = None
    makeup: Optional[List[str]] = None
    poses: Optional[List[str]] = None
    summary: Optional[str] = None
    history: Optional[dict] = None

