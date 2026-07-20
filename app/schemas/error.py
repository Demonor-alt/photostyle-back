from typing import Any, Optional

from fastapi import HTTPException
from pydantic import Field

from .base import BaseSchema


class ErrorDetail(BaseSchema):  # 定义错误详情模型
    type: str = Field(..., description="错误类型")
    message: str = Field(..., description="错误信息")
    hint: Optional[str] = Field(None, description="错误提示")


class ApiError(HTTPException):  # 定义统一的API错误异常基类
    def __init__(
        self,
        status_code: int,
        error_type: str,
        message: str,
        hint: Optional[str] = None,
    ):
        detail = {"type": error_type, "message": message}
        if hint:
            detail["hint"] = hint
        super().__init__(status_code=status_code, detail=detail)


# ========== 400 错误（客户端请求错误）==========


class BadRequestError(ApiError):  # 400 错误基类
    def __init__(self, error_type: str, message: str, hint: Optional[str] = None):
        super().__init__(400, error_type, message, hint)


class UploadError(BadRequestError):  # 上传错误
    def __init__(self, message: str = "上传失败", hint: Optional[str] = None):
        super().__init__("upload_error", message, hint)


class FaceNotDetectedError(BadRequestError):  # 人脸未检测到错误
    def __init__(self, message: str = "图片未检测到人脸", hint: Optional[str] = None):
        super().__init__("face_not_detected", message, hint)


class FeedbackError(BadRequestError):  # 反馈错误
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__("feedback_error", message, hint)


class RegisterError(BadRequestError):  # 注册错误
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__("register_error", message, hint)


class LoginError(BadRequestError):  # 登录错误
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__("login_error", message, hint)


# ========== 401 错误（认证失败）==========


class UnauthorizedError(ApiError):  # 401 认证错误
    def __init__(self, message: str = "用户名或密码错误", hint: Optional[str] = None):
        super().__init__(401, "login_error", message, hint)


# ========== 500 错误（服务器内部错误）==========


class InternalServerError(ApiError):  # 500 错误基类
    def __init__(self, error_type: str, message: str, hint: Optional[str] = None):
        super().__init__(500, error_type, message, hint)


class UploadUnknownError(InternalServerError):  # 上传未知错误
    def __init__(self, message: str = "照片上传失败", hint: Optional[str] = None):
        super().__init__("upload_unknown_error", message, hint)


class HistorySaveError(InternalServerError):  # 历史记录保存错误
    def __init__(
        self, message: str = "推荐结果已生成，但历史记录保存失败", hint: Optional[str] = None
    ):
        super().__init__("history_save_error", message, hint)


class RegisterUnknownError(InternalServerError):  # 注册未知错误
    def __init__(self, message: str = "注册失败，服务器内部错误", hint: Optional[str] = None):
        super().__init__("register_unknown_error", message, hint)


class LoginUnknownError(InternalServerError):  # 登录未知错误
    def __init__(self, message: str = "登录失败，服务器内部错误", hint: Optional[str] = None):
        super().__init__("login_unknown_error", message, hint)


# ========== 503 错误（服务不可用）==========


class ServiceUnavailableError(ApiError):  # 503 服务不可用错误
    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(503, "database_unavailable", message, hint)


class DatabaseUnavailableError(ServiceUnavailableError):  # 数据库不可用错误
    def __init__(
        self, message: str = "服务暂时不可用：数据库连接失败，请稍后重试", hint: Optional[str] = None
    ):
        super().__init__(message, hint)
