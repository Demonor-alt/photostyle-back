import logging  # 引入logging用于记录接口调用信息
from pathlib import Path  # 引入Path用于处理临时文件保存路径

from fastapi import APIRouter, Depends  # 引入路由与依赖注入能力
from fastapi.responses import FileResponse  # 引入文件响应

from app.schemas.base import ApiResponse  # 引入统一响应模型
from app.schemas.error import (
    DatabaseUnavailableError,
    FaceNotDetectedError,
    LoginError,
    LoginUnknownError,
    RegisterError,
    RegisterUnknownError,
    UnauthorizedError,
    UploadError,
    UploadUnknownError,
)
from app.schemas.user import (
    GetUserApiResponse,
    LoginApiResponse,
    LoginRequest,
    RegisterApiResponse,
    RegisterRequest,
    UpdateUserApiResponse,
    UpdateUserProfileRequest,
    UploadPhotoApiResponse,
    UploadPhotoData,
    UploadPhotoFormParams,
    UserResponse,
)
from app.db.user_service import (
    ensure_user,
    get_user_profile,
    login_user,
    upsert_user_photo,
    update_user_profile,
)
from app.services.qwen_face_client import analyze_image  # 引入Qwen图片分析服务
from app.api.utils import save_upload_file  # 引入文件上传工具函数

logger = logging.getLogger(__name__)  # 创建路由模块日志器

router = APIRouter()  # 创建路由实例


@router.post("/photos/upload", response_model=UploadPhotoApiResponse)
async def upload_photo(
    form: UploadPhotoFormParams = Depends(),
) -> UploadPhotoApiResponse:
    image = form.image
    if not image.content_type or not image.content_type.startswith("image/"):
        raise UploadError("只支持图片文件上传")
    image_path, image_mime_type = save_upload_file(image)
    try:
        face_analysis = analyze_image(image_path=image_path, image_mime_type=image_mime_type)
        # 只有检测到人脸时才把照片写入数据库，避免无效照片污染用户资料
        user = upsert_user_photo(form.username, image_path, image_mime_type, face_analysis)
    except ValueError as exc:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
        error_message = str(exc)
        if error_message == "图片未检测到人脸":
            raise FaceNotDetectedError() from exc
        raise UploadError(error_message) from exc
    except Exception as exc:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
        raise UploadUnknownError(hint=str(exc)) from exc
    
    return UploadPhotoApiResponse(
        data=UploadPhotoData(
            username=user["username"],
            photo_path=user.get("photo_path"),
            photo_mime_type=user.get("photo_mime_type"),
            face_analysis=face_analysis,
        )
    )


@router.post("/auth/register", response_model=RegisterApiResponse)  # 定义注册接口
async def register_user(payload: RegisterRequest) -> RegisterApiResponse:  # 接收注册请求
    try:
        user = ensure_user(payload.username, payload.password)  # 创建或获取用户
        return RegisterApiResponse(data=UserResponse(**user))
    except ValueError as exc:
        raise RegisterError(str(exc)) from exc
    except Exception as exc:
        raise RegisterUnknownError(hint=str(exc)) from exc


@router.post("/auth/login", response_model=LoginApiResponse)  # 定义登录接口
async def login(payload: LoginRequest) -> LoginApiResponse:  # 接收登录请求
    try:
        user = login_user(payload.username, payload.password)  # 校验用户名密码
        return LoginApiResponse(data=UserResponse(**user))
    except ValueError as exc:
        message = str(exc)
        if message == "用户名或密码错误":
            raise UnauthorizedError() from exc
        raise LoginError(message) from exc
    except Exception as exc:
        raise LoginUnknownError(hint=str(exc)) from exc


@router.get("/auth/me", response_model=GetUserApiResponse)  # 定义当前用户接口
async def me(username: str) -> GetUserApiResponse:  # 通过用户名获取当前用户
    user = get_user_profile(username)  # 查询用户资料
    return GetUserApiResponse(data=UserResponse(**user))


@router.put("/auth/me", response_model=UpdateUserApiResponse)  # 定义资料修改接口
async def update_me(username: str, payload: UpdateUserProfileRequest) -> UpdateUserApiResponse:  # 修改当前用户资料
    user = update_user_profile(
        username,
        new_username=payload.new_username,
        password=payload.password,
        photo_path=payload.photo_path,
        photo_mime_type=payload.photo_mime_type,
        face_analysis=payload.face_analysis,
    )
    return UpdateUserApiResponse(data=UserResponse(**user))


@router.get("/photos/preview")  # 定义本地图片预览接口
async def photo_preview(path: str):  # 通过路径读取本地图片
    file_path = Path(path)  # 转为Path对象
    if not file_path.exists():  # 如果文件不存在
        raise ValueError("图片文件不存在")  # 直接报错
    return FileResponse(str(file_path))  # 返回文件内容
