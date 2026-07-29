import json  # 引入json用于构造SSE数据
from app.utils.runtime import logger
from fastapi import APIRouter, Depends  # 引入路由与依赖注入能力
from pydantic import BaseModel  # 引入Pydantic基础模型
from fastapi.responses import StreamingResponse  # 引入流式响应

from app.schemas.history import (
    CreateHistoryApiResponse,
    DatabaseStatusApiResponse,
    DatabaseStatusResponse,
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
from app.services.orchestrator import format_sse_event, run_pipeline  # 引入调度入口和SSE格式化器
from app.db.history_mapper import (  # 引入历史数据服务
    get_database_status,
    list_history_records,
    save_history_record,
    update_history_feedback,
)
from app.db.user_mapper import get_user_profile  # 引入用户查询服务
from app.rabbitmq.feedback_tasks import publish_feedback_updated  # 引入反馈异步任务发布器
from app.api.utils import save_upload_file, parse_tag_list  # 引入工具函数

router = APIRouter()  # 创建路由实例


class FeedbackUpdateRequest(BaseModel):
    makeup_rating: int = 0
    outfit_rating: int = 0
    pose_rating: int = 0
    feedback_comment: str | None = None


@router.post("/suggest", response_model=SuggestApiResponse)  # 定义建议生成接口
async def suggest(  # 定义支持表单上传的建议接口
    form: SuggestFormParams = Depends(),
) -> SuggestApiResponse:  # 返回建议响应
    image_path = None  # 初始化图片路径
    image_mime_type = None  # 初始化图片MIME类型
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

        history = save_history_record({
            "user_id": user["id"],
            "input_data": input_data,
            "output_data": result.model_dump(),
            "makeup_rating": 0,
            "outfit_rating": 0,
            "pose_rating": 0,
            "feedback_comment": None,
            "reviewed": False,
        })
    except Exception as exc:
        logger.exception("suggest.history.save_failed")
        raise HistorySaveError(hint=str(exc)) from exc
    
    return SuggestApiResponse(data={**result.model_dump(), "history": history})


# @router.post("/suggest/stream")  # 定义流式建议生成接口
# async def suggest_stream(  # 定义SSE流式接口
#     form: SuggestFormParams = Depends(),
# ) -> StreamingResponse:  # 返回SSE响应
#     image_path = None  # 初始化图片路径
#     image_mime_type = None  # 初始化图片MIME类型
#     if form.image is not None:  # 如果前端上传了文件
#         image_path, image_mime_type = save_upload_file(form.image)  # 保存图片到本地
#     payload = SuggestRequest(  # 组装请求模型
#         username=form.username,  # 传入用户名
#         image_path=image_path,  # 传入图片路径
#         image_mime_type=image_mime_type,  # 传入MIME类型
#         style=form.style,  # 传入风格
#         location=form.location,  # 传入地点
#         time=form.time,  # 传入时间
#         weather=form.weather,  # 传入天气
#         face_tags=parse_tag_list(form.face_tags),  # 解析人脸标签
#         shot_tags=parse_tag_list(form.shot_tags),  # 解析画幅标签
#         pose_tags=parse_tag_list(form.pose_tags),  # 解析姿势标签
#         extra_tags=parse_tag_list(form.extra_tags),  # 解析全部附加选择项
#     )  # 请求组装结束
#     logger.info("suggest.stream.request=%s", payload.model_dump_json(ensure_ascii=False))

#     def event_generator():  # 定义SSE事件生成器
#         try:
#             yield format_sse_event("status", {"message": "started"})  # 发送开始状态
#             for chunk in stream_pipeline(payload):  # 遍历LangGraph流式输出
#                 logger.info("suggest.stream.chunk=%s", json.dumps(chunk, ensure_ascii=False, default=str))
#                 yield format_sse_event("chunk", chunk)  # 发送每个步骤chunk
#             yield format_sse_event("done", {"message": "completed"})  # 发送完成状态
#         except Exception as exc:  # 捕获流中任何异常，防止 chunked 流被静默中断
#             import traceback
#             traceback.print_exc()
#             logger.exception("suggest.stream.error")
#             yield format_sse_event("error", {"message": str(exc)})  # 将错误通过 SSE 发给前端

#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
#     )


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
async def get_history(user_id: int | None = None) -> GetHistoryApiResponse:  # 获取历史记录列表，支持按用户ID筛选
    items = list_history_records(user_id=user_id)  # 按用户ID筛选历史记录
    return GetHistoryApiResponse(
        data=HistoryListResponse(items=items)
    )


@router.post("/history/{history_id}/feedback", response_model=MessageResponse)
async def update_history(history_id: int, payload: FeedbackUpdateRequest) -> MessageResponse:
    update_history_feedback(  # 更新历史记录并获取最新数据
        history_id,  # 传入历史ID
        payload.makeup_rating,  # 传入妆容评分
        payload.outfit_rating,  # 传入穿搭评分
        payload.pose_rating,  # 传入姿势评分
        payload.feedback_comment,  # 传入点评内容
    )  # 更新结束
    
    logger.info("feedback.update.publishing history_id=%s", history_id)  # 记录开始发布反馈更新事件
    try:
        publish_feedback_updated(history_id)  # 将后续向量写入等操作交给 RabbitMQ 消费者异步执行
        logger.info("feedback.update.published history_id=%s", history_id)  # 记录成功发布事件
    except Exception as exc:
        logger.exception("feedback.update.publish_failed history_id=%s, error=%s", history_id, str(exc))
        raise FeedbackError(hint=f"发布反馈更新事件失败: {exc}") from exc
    
    return MessageResponse(message="点评保存成功")