from typing import Optional  # 引入类型标注用于描述字段结构
from datetime import datetime  # 引入datetime用于描述时间字段

from app.schemas.base import BaseSchema  # 引入公共Schema基类

#/photos/upload接口数据
class UploadPhotoData(BaseSchema):  # 定义照片上传响应数据
    username: str  # 用户名
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果
    simple_analysis: Optional[dict] = None  # 简化人脸分析结果

#/auth/me接口数据
class UserResponse(BaseSchema):  # 定义用户响应模型
    id: int  # 用户ID
    username: str  # 用户名
    photo_path: Optional[str] = None  # 图片路径
    photo_mime_type: Optional[str] = None  # 图片类型
    face_analysis: Optional[dict] = None  # 人脸分析结果
    simple_analysis: Optional[dict] = None  # 简化人脸分析结果
    created_at: Optional[datetime] = None  # 创建时间
    updated_at: Optional[datetime] = None  # 更新时间