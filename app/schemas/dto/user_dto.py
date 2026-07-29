from typing_extensions import Annotated  # 引入Annotated用于类型标注
from fastapi import File, Form, UploadFile  # 引入FastAPI表单和文件处理
from typing import Optional  # 引入类型标注用于描述字段结构


from app.schemas.base import BaseSchema  # 引入公共Schema基类

#/photos/upload接口表单参数
class UploadPhotoFormParams:  # 定义照片上传表单参数（用于FastAPI依赖注入）
    def __init__(
        self,
        username: Annotated[str, Form(description="用户名")],
        image: Annotated[UploadFile, File(description="上传的图片文件")],
    ):
        self.username = username
        self.image = image


#/auth/register接口表单参数
class RegisterRequest(BaseSchema):  # 定义注册请求模型
    username: str  # 用户名
    password: Optional[str] = None  # 密码，可选，未传时使用默认密码


#/auth/login接口表单参数
class LoginRequest(BaseSchema):  # 定义登录请求模型
    username: str  # 用户名
    password: str  # 密码


#/auth/me的put接口表单参数
class UpdateUserProfileRequest(BaseSchema):  # 定义更新用户资料请求模型
    new_username: Optional[str] = None  # 新用户名
    password: Optional[str] = None  # 新密码
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果
    simple_analysis: Optional[dict] = None  # 简化人脸分析结果