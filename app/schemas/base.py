from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field  # 引入Pydantic用于定义请求响应模型

T = TypeVar("T")


class BaseSchema(BaseModel):  # 定义公共Schema基类
    """公共Schema基类，提供通用配置"""
    
    class Config:
        from_attributes = True  # 允许从ORM模型自动转换


class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    success: bool = Field(default=True, description="请求是否成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")
