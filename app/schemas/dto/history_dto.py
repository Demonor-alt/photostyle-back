from typing_extensions import Annotated  # 引入Annotated用于类型标注
from fastapi import File, Form, UploadFile  # 引入FastAPI表单和文件处理
from typing import Optional  # 引入类型标注用于描述字段结构
from pydantic import Field  # 引入 Field 用于默认工厂
from app.schemas.base import BaseSchema  # 引入公共Schema基类
from app.schemas.orm.history import PhotoStyleInputData, PhotoStyleOutputData  # 引入结构化历史数据模型

#/suggest接口表单参数
class SuggestFormParams:  # 定义建议生成表单参数（用于FastAPI依赖注入）
    def __init__(
        self,
        username: Annotated[str, Form(description="用户名")],
        user_id: Annotated[int, Form(description="用户ID")],
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
        self.user_id = user_id
        self.style = style
        self.location = location
        self.time = time
        self.weather = weather
        self.face_tags = face_tags
        self.shot_tags = shot_tags
        self.pose_tags = pose_tags
        self.extra_tags = extra_tags
        self.image = image


#/history的post接口表单参数
class HistoryRecord(BaseSchema):  # 定义历史记录模型
    id: Optional[int] = None  # 历史记录ID
    user_id: int  # 用户ID
    input_data: PhotoStyleInputData = Field(default_factory=PhotoStyleInputData)  # 输入数据
    output_data: PhotoStyleOutputData = Field(default_factory=PhotoStyleOutputData)  # 输出数据
    makeup_rating: int = 0  # 妆容评分
    outfit_rating: int = 0  # 穿搭评分
    pose_rating: int = 0  # 姿势评分
    feedback_comment: Optional[str] = None  # 点评内容
    reviewed: bool = False  # 是否已点评
    created_at: Optional[str] = None  # 创建时间

#/history/{history_id}/feedback接口表单参数
class FeedbackUpdateRequest(BaseSchema):  # 定义反馈更新请求模型
    makeup_rating: int = 0  # 妆容评分
    outfit_rating: int = 0  # 穿搭评分
    pose_rating: int = 0  # 姿势评分
    feedback_comment: Optional[str] = None  # 点评内容
