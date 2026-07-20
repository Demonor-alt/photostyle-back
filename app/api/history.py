import json  # 引入json用于构造SSE数据
import logging  # 引入logging用于记录接口调用信息

from fastapi import APIRouter, Depends  # 引入路由与依赖注入能力
from fastapi.responses import StreamingResponse  # 引入流式响应

from app.schemas.history import (
    CreateHistoryApiResponse,
    DatabaseStatusApiResponse,
    DatabaseStatusResponse,
    FeedbackApiResponse,
    FeedbackRequest,
    FeedbackResponse,
    GetHistoryApiResponse,
    HistoryListResponse,
    HistoryRecord,
    MessageResponse,
    SuggestApiResponse,
    SuggestFormParams,
    SuggestRequest,
)
from app.schemas.error import (
    FeedbackError,
    HistorySaveError,
)
from app.services.orchestrator import format_sse_event, run_pipeline, stream_pipeline  # 引入调度入口和SSE格式化器
from app.db.history_service import (
    get_database_status,
    list_history_records,
    save_history_record,
    update_history_feedback,
)
from app.db.user_service import get_user_profile  # 引入用户查询服务
from app.api.utils import save_upload_file, parse_tag_list  # 引入工具函数

logger = logging.getLogger(__name__)  # 创建路由模块日志器

router = APIRouter()  # 创建路由实例


@router.post("/suggest", response_model=SuggestApiResponse)  # 定义建议生成接口
async def suggest(  # 定义支持表单上传的建议接口
    form: SuggestFormParams = Depends(),
) -> SuggestApiResponse:  # 返回建议响应
    image_path = None  # 初始化图片路径
    image_mime_type = None  # 初始化图片MIME类型
    if form.image is not None:  # 如果前端上传了文件
        image_path, image_mime_type = save_upload_file(form.image)  # 保存图片到本地
    payload = SuggestRequest(  # 组装请求模型
        username=form.username,  # 传入用户名
        image_path=image_path,  # 传入图片路径
        image_mime_type=image_mime_type,  # 传入MIME类型
        style=form.style,  # 传入风格
        location=form.location,  # 传入地点
        time=form.time,  # 传入时间
        weather=form.weather,  # 传入天气
        face_tags=parse_tag_list(form.face_tags),  # 解析人脸标签
        shot_tags=parse_tag_list(form.shot_tags),  # 解析画幅标签
        pose_tags=parse_tag_list(form.pose_tags),  # 解析姿势标签
        extra_tags=parse_tag_list(form.extra_tags),  # 解析全部附加选择项
    )  # 请求组装结束
    logger.info("suggest.request=%s", payload.model_dump_json())
    result = run_pipeline(payload)  # 调用调度流程生成建议
    logger.info("suggest.response=%s", result.model_dump_json())
    try:
        # 获取用户ID
        user = get_user_profile(payload.username)
        # 准备input_data，移除face_analysis和username，清空extra_tags
        input_data = payload.model_dump()
        input_data.pop("face_analysis", None)
        input_data.pop("username", None)
        input_data["extra_tags"] = []
        
        save_history_record({
            "user_id": user["id"],
            "input_data": input_data,
            "output_data": result.model_dump(),
            "liked": False,
            "shot_success": False,
        })
    except Exception as exc:
        logger.exception("suggest.history.save_failed")
        raise HistorySaveError(hint=str(exc)) from exc
    
    return SuggestApiResponse(data=result)


@router.post("/suggest/stream")  # 定义流式建议生成接口
async def suggest_stream(  # 定义SSE流式接口
    form: SuggestFormParams = Depends(),
) -> StreamingResponse:  # 返回SSE响应
    image_path = None  # 初始化图片路径
    image_mime_type = None  # 初始化图片MIME类型
    if form.image is not None:  # 如果前端上传了文件
        image_path, image_mime_type = save_upload_file(form.image)  # 保存图片到本地
    payload = SuggestRequest(  # 组装请求模型
        username=form.username,  # 传入用户名
        image_path=image_path,  # 传入图片路径
        image_mime_type=image_mime_type,  # 传入MIME类型
        style=form.style,  # 传入风格
        location=form.location,  # 传入地点
        time=form.time,  # 传入时间
        weather=form.weather,  # 传入天气
        face_tags=parse_tag_list(form.face_tags),  # 解析人脸标签
        shot_tags=parse_tag_list(form.shot_tags),  # 解析画幅标签
        pose_tags=parse_tag_list(form.pose_tags),  # 解析姿势标签
        extra_tags=parse_tag_list(form.extra_tags),  # 解析全部附加选择项
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


@router.get("/db/status", response_model=DatabaseStatusApiResponse)  # 定义数据库状态接口
async def database_status() -> DatabaseStatusApiResponse:  # 返回数据库状态
    status = get_database_status()  # 获取数据库连接信息
    return DatabaseStatusApiResponse(
        data=DatabaseStatusResponse(**status)
    )


@router.post("/history", response_model=CreateHistoryApiResponse)  # 定义历史记录保存接口
async def create_history(record: HistoryRecord) -> CreateHistoryApiResponse:  # 接收历史记录并保存
    save_history_record(record.model_dump())  # 将记录写入存储
    return CreateHistoryApiResponse(
        data=MessageResponse(message="历史记录保存成功")
    )


@router.get("/history", response_model=GetHistoryApiResponse)  # 定义历史记录查询接口
async def get_history(username: str | None = None) -> GetHistoryApiResponse:  # 获取历史记录列表，支持按用户名筛选
    user_id = None
    if username:  # 如果提供了用户名
        user = get_user_profile(username)  # 获取用户信息
        user_id = user["id"]  # 提取用户ID
    items = list_history_records(user_id=user_id)  # 按用户ID筛选历史记录
    return GetHistoryApiResponse(
        data=HistoryListResponse(items=items)
    )


@router.post("/feedback", response_model=FeedbackApiResponse)  # 定义反馈提交接口
async def submit_feedback(payload: FeedbackRequest) -> FeedbackApiResponse:  # 接收用户反馈
    if payload.history_id is None:  # 如果没有提供历史记录ID
        raise FeedbackError("必须提供 history_id")
    update_history_feedback(payload.history_id, payload.liked, payload.shot_success)  # 更新历史记录反馈
    return FeedbackApiResponse(
        data=FeedbackResponse(message="feedback saved", liked=payload.liked, shot_success=payload.shot_success)
    )
