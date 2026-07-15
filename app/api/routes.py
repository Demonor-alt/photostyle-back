import json  # 引入json用于解析表单中的标签数据与构造SSE数据
import logging  # 引入logging用于记录接口调用信息
from pathlib import Path  # 引入Path用于处理临时文件保存路径
from uuid import uuid4  # 引入uuid用于生成临时文件名

from fastapi import APIRouter, File, Form, HTTPException, UploadFile  # 引入路由与文件上传能力
from fastapi.responses import FileResponse, StreamingResponse  # 引入文件与流式响应
from pydantic import ValidationError  # 引入Pydantic校验异常，便于返回更清晰的参数错误

from app.models import FeedbackRequest, HistoryRecord, LoginRequest, RegisterRequest, SuggestRequest, SuggestResponse, UpdateUserProfileRequest, UserResponse  # 引入请求响应模型
from app.services.orchestrator import format_sse_event, run_pipeline, stream_pipeline  # 引入调度入口和SSE格式化器
from app.db.history_service import get_database_status, list_history_records, save_history_record  # 引入历史记录服务
from app.db.user_service import ensure_user, get_user_profile, login_user, upsert_user_photo, update_user_profile  # 引入登录注册服务
from app.services.qwen_face_client import analyze_image  # 引入Qwen图片分析服务

logger = logging.getLogger(__name__)  # 创建路由模块日志器

router = APIRouter()  # 创建路由实例


def _save_upload_file(upload: UploadFile) -> tuple[str, str]:  # 保存上传文件到本地临时目录
    suffix = Path(upload.filename or "image.jpg").suffix or ".jpg"  # 获取文件后缀
    target_dir = Path(__file__).resolve().parents[2] / "uploads"  # 定位临时目录
    target_dir.mkdir(parents=True, exist_ok=True)  # 如果目录不存在则创建
    target_path = target_dir / f"{uuid4().hex}{suffix}"  # 生成唯一文件名
    content = upload.file.read()  # 读取上传文件内容
    target_path.write_bytes(content)  # 写入本地文件
    mime_type = upload.content_type or "image/jpeg"  # 记录MIME类型
    return str(target_path), mime_type  # 返回文件路径和MIME类型


def _parse_tag_list(raw_value: str) -> list[str]:  # 解析前端传来的JSON标签字符串
    try:  # 尝试正常解析
        value = json.loads(raw_value)  # 将JSON字符串转换为列表
        if isinstance(value, list):  # 如果结果是列表
            return [str(item).strip() for item in value if str(item).strip()]  # 规范成字符串列表
        raise ValueError("标签字段必须是 JSON 数组")  # 直接暴露格式错误
    except Exception as exc:  # 如果解析失败
        raise ValueError(f"标签字段解析失败: {raw_value}") from exc  # 不再静默吞掉异常


@router.post("/photos/upload")
async def upload_photo(
    username: str = Form(...),
    image: UploadFile = File(...),
) -> dict:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail={"type": "upload_error", "message": "只支持图片文件上传"})
    image_path, image_mime_type = _save_upload_file(image)
    try:
        face_analysis = analyze_image(image_path=image_path, image_mime_type=image_mime_type)
        # 只有检测到人脸时才把照片写入数据库，避免无效照片污染用户资料
        user = upsert_user_photo(username, image_path, image_mime_type, face_analysis)
    except ValueError as exc:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
        error_message = str(exc)
        if error_message == "图片未检测到人脸":
            raise HTTPException(status_code=400, detail={"type": "face_not_detected", "message": error_message}) from exc
        raise HTTPException(status_code=400, detail={"type": "upload_error", "message": error_message}) from exc
    except ConnectionError as exc:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
        raise HTTPException(
            status_code=503,
            detail={"type": "database_unavailable", "message": "上传暂时不可用：数据库连接失败，请稍后重试", "hint": str(exc)},
        ) from exc
    except Exception as exc:
        if image_path:
            try:
                Path(image_path).unlink(missing_ok=True)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail={"type": "upload_unknown_error", "message": "照片上传失败", "hint": str(exc)}) from exc
    return {
        "success": True,
        "message": "photo uploaded",
        "username": user["username"],
        "photo_path": user.get("photo_path"),
        "photo_mime_type": user.get("photo_mime_type"),
        "face_analysis": face_analysis,
    }


@router.post("/suggest", response_model=SuggestResponse)  # 定义建议生成接口
async def suggest(  # 定义支持表单上传的建议接口
    username: str = Form(...),  # 接收用户名字段
    style: str = Form(...),  # 接收风格字段
    location: str | None = Form(None),  # 接收地点字段
    time: str | None = Form(None),  # 接收时间字段
    weather: str | None = Form(None),  # 接收天气字段
    face_tags: str = Form("[]"),  # 接收人脸标签JSON字符串
    shot_tags: str = Form("[]"),  # 接收画幅标签JSON字符串
    pose_tags: str = Form("[]"),  # 接收姿势标签JSON字符串
    extra_tags: str = Form("[]"),  # 接收前端全部选择项
    image: UploadFile | None = File(None),  # 接收上传图片文件
) -> SuggestResponse:  # 返回建议响应
    image_path = None  # 初始化图片路径
    image_mime_type = None  # 初始化图片MIME类型
    if image is not None:  # 如果前端上传了文件
        image_path, image_mime_type = _save_upload_file(image)  # 保存图片到本地
    payload = SuggestRequest(  # 组装请求模型
        username=username,  # 传入用户名
        image_path=image_path,  # 传入图片路径
        image_mime_type=image_mime_type,  # 传入MIME类型
        style=style,  # 传入风格
        location=location,  # 传入地点
        time=time,  # 传入时间
        weather=weather,  # 传入天气
        face_tags=_parse_tag_list(face_tags),  # 解析人脸标签
        shot_tags=_parse_tag_list(shot_tags),  # 解析画幅标签
        pose_tags=_parse_tag_list(pose_tags),  # 解析姿势标签
        extra_tags=_parse_tag_list(extra_tags),  # 解析全部附加选择项
    )  # 请求组装结束
    logger.info("suggest.request=%s", payload.model_dump_json())
    result = run_pipeline(payload)  # 调用调度流程生成建议
    logger.info("suggest.response=%s", result.model_dump_json())
    try:
        save_history_record({
            "input_data": payload.model_dump(),
            "output_data": result.model_dump(),
            "liked": False,
            "shot_success": False,
        })
    except Exception as exc:
        logger.exception("suggest.history.save_failed")
        raise HTTPException(status_code=500, detail={"type": "history_save_error", "message": "推荐结果已生成，但历史记录保存失败", "hint": str(exc)}) from exc
    return result


@router.post("/suggest/stream")  # 定义流式建议生成接口
async def suggest_stream(  # 定义SSE流式接口
    username: str = Form(...),  # 接收用户名字段
    style: str = Form(...),  # 接收风格字段
    location: str | None = Form(None),  # 接收地点字段
    time: str | None = Form(None),  # 接收时间字段
    weather: str | None = Form(None),  # 接收天气字段
    face_tags: str = Form("[]"),  # 接收人脸标签JSON字符串
    shot_tags: str = Form("[]"),  # 接收画幅标签JSON字符串
    pose_tags: str = Form("[]"),  # 接收姿势标签JSON字符串
    extra_tags: str = Form("[]"),  # 接收前端全部选择项
    image: UploadFile | None = File(None),  # 接收上传图片文件
) -> StreamingResponse:  # 返回SSE响应
    image_path = None  # 初始化图片路径
    image_mime_type = None  # 初始化图片MIME类型
    if image is not None:  # 如果前端上传了文件
        image_path, image_mime_type = _save_upload_file(image)  # 保存图片到本地
    payload = SuggestRequest(  # 组装请求模型
        username=username,  # 传入用户名
        image_path=image_path,  # 传入图片路径
        image_mime_type=image_mime_type,  # 传入MIME类型
        style=style,  # 传入风格
        location=location,  # 传入地点
        time=time,  # 传入时间
        weather=weather,  # 传入天气
        face_tags=_parse_tag_list(face_tags),  # 解析人脸标签
        shot_tags=_parse_tag_list(shot_tags),  # 解析画幅标签
        pose_tags=_parse_tag_list(pose_tags),  # 解析姿势标签
        extra_tags=_parse_tag_list(extra_tags),  # 解析全部附加选择项
    )  # 请求组装结束
    logger.info("suggest.stream.request=%s", payload.model_dump_json(ensure_ascii=False))

    def event_generator():  # 定义SSE事件生成器
        try:
            yield format_sse_event("status", {"message": "started"})  # 发送开始状态
            for chunk in stream_pipeline(payload):  # 遍历LangGraph流式输出
                logger.info("suggest.stream.chunk=%s", json.dumps(chunk, ensure_ascii=False, default=str))
                yield format_sse_event("chunk", chunk)  # 发送每个步骤chunk
            yield format_sse_event("done", {"message": "completed"})  # 发送完成状态
        except Exception as exc:  # 捕获流中任何异常，防止 chunked 流被静默中断
            import traceback
            traceback.print_exc()
            logger.exception("suggest.stream.error")
            yield format_sse_event("error", {"message": str(exc)})  # 将错误通过 SSE 发给前端

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/db/status")  # 定义数据库状态接口
async def database_status() -> dict:  # 返回数据库状态
    return get_database_status()  # 返回数据库连接信息


@router.post("/history")  # 定义历史记录保存接口
async def create_history(record: HistoryRecord) -> dict:  # 接收历史记录并保存
    save_history_record(record.model_dump())  # 将记录写入存储
    return {"message": "history saved"}  # 返回保存结果


@router.get("/history")  # 定义历史记录查询接口
async def get_history() -> dict:  # 获取历史记录列表
    return {"items": list_history_records()}  # 返回历史记录集合


@router.post("/auth/register", response_model=UserResponse)  # 定义注册接口
async def register_user(payload: RegisterRequest) -> UserResponse:  # 接收注册请求
    try:
        user = ensure_user(payload.username, payload.password)  # 创建或获取用户
        return UserResponse(**user)  # 返回用户信息
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"type": "register_error", "message": str(exc)}) from exc
    except ConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "type": "database_unavailable",
                "message": "注册暂时不可用：数据库连接失败，请检查 MySQL 配置和数据库是否已创建",
                "hint": str(exc),
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"type": "register_unknown_error", "message": "注册失败，服务器内部错误", "hint": str(exc)},
        ) from exc


@router.post("/auth/login", response_model=UserResponse)  # 定义登录接口
async def login(payload: LoginRequest) -> UserResponse:  # 接收登录请求
    try:
        user = login_user(payload.username, payload.password)  # 校验用户名密码
        return UserResponse(**user)  # 返回用户信息
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    except ValueError as exc:
        message = str(exc)
        status_code = 401 if message == "用户名或密码错误" else 400
        raise HTTPException(status_code=status_code, detail={"type": "login_error", "message": message}) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"type": "login_unknown_error", "message": "登录失败，服务器内部错误", "hint": str(exc)},
        ) from exc


@router.get("/auth/me", response_model=UserResponse)  # 定义当前用户接口
async def me(username: str) -> UserResponse:  # 通过用户名获取当前用户
    user = get_user_profile(username)  # 查询用户资料
    return UserResponse(**user)  # 返回用户信息


@router.put("/auth/me", response_model=UserResponse)  # 定义资料修改接口
async def update_me(username: str, payload: UpdateUserProfileRequest) -> UserResponse:  # 修改当前用户资料
    user = update_user_profile(
        username,
        new_username=payload.new_username,
        password=payload.password,
        photo_path=payload.photo_path,
        photo_mime_type=payload.photo_mime_type,
        face_analysis=payload.face_analysis,
    )
    return UserResponse(**user)


@router.get("/photos/preview")  # 定义本地图片预览接口
async def photo_preview(path: str):  # 通过路径读取本地图片
    file_path = Path(path)  # 转为Path对象
    if not file_path.exists():  # 如果文件不存在
        raise ValueError("图片文件不存在")  # 直接报错
    return FileResponse(str(file_path))  # 返回文件内容


@router.post("/feedback")  # 定义反馈提交接口
async def submit_feedback(payload: FeedbackRequest) -> dict:  # 接收用户反馈
    save_history_record(payload.model_dump())  # 当前将反馈也纳入历史存储，方便后续分析
    return {"message": "feedback saved", "liked": payload.liked, "shot_success": payload.shot_success}  # 返回保存结果
