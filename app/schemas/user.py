from datetime import datetime  # 引入datetime用于描述时间字段
from typing import Optional  # 引入类型标注用于描述字段结构

from fastapi import File, Form, UploadFile  # 引入FastAPI表单和文件处理
from pydantic import Field  # 引入Field用于字段描述
from typing_extensions import Annotated  # 引入Annotated用于类型标注

from .base import BaseSchema  # 引入公共Schema基类


class LoginRequest(BaseSchema):  # 定义登录请求模型
    username: str  # 用户名
    password: str  # 密码


class RegisterRequest(BaseSchema):  # 定义注册请求模型
    username: str  # 用户名
    password: Optional[str] = None  # 密码，可选，未传时使用默认密码


class UpdateUserProfileRequest(BaseSchema):  # 定义更新用户资料请求模型
    new_username: Optional[str] = None  # 新用户名
    password: Optional[str] = None  # 新密码
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果


class UploadPhotoFormParams:  # 定义照片上传表单参数（用于FastAPI依赖注入）
    def __init__(
        self,
        username: Annotated[str, Form(description="用户名")],
        image: Annotated[UploadFile, File(description="上传的图片文件")],
    ):
        self.username = username
        self.image = image


class UploadPhotoRequest(BaseSchema):  # 定义照片上传请求模型
    username: str = Field(..., description="用户名")


class UploadPhotoData(BaseSchema):  # 定义照片上传响应数据
    username: str  # 用户名
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果


class UserResponse(BaseSchema):  # 定义用户响应模型
    id: int  # 用户ID
    username: str  # 用户名
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果
    created_at: Optional[datetime] = None  # 创建时间
    updated_at: Optional[datetime] = None  # 更新时间


class PhotoPreviewRequest(BaseSchema):  # 定义图片预览请求模型
    path: str = Field(..., description="图片文件路径")


# ========== 接口专用响应模型 ==========


class UploadPhotoApiResponse(BaseSchema):  # /photos/upload 接口响应
    success: bool = True
    message: str = "照片上传成功"
    data: UploadPhotoData


class RegisterApiResponse(BaseSchema):  # /auth/register 接口响应
    success: bool = True
    message: str = "注册成功"
    data: UserResponse


class LoginApiResponse(BaseSchema):  # /auth/login 接口响应
    success: bool = True
    message: str = "登录成功"
    data: UserResponse


class GetUserApiResponse(BaseSchema):  # /auth/me GET 接口响应
    success: bool = True
    message: str = "用户信息获取成功"
    data: UserResponse


class UpdateUserApiResponse(BaseSchema):  # /auth/me PUT 接口响应
    success: bool = True
    message: str = "用户资料更新成功"
    data: UserResponse
