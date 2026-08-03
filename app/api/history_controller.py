from app.utils.runtime import logger
from fastapi import APIRouter, Depends  # 引入路由与依赖注入能力

from app.schemas.base import ApiResponse
from app.schemas.llm import (SuggestRequest)
from app.schemas.dto.history_dto import (SuggestFormParams,HistoryRecord,FeedbackUpdateRequest)
from app.schemas.dto.history_user_dto import HistoryUserRecord
from app.schemas.orm.history import PhotoStyleInputData, PhotoStyleOutputData
from app.schemas.vo.history_vo import (SuggestApiData, HistoryListResponse, DatabaseStatusResponse)
from app.schemas.error import (FeedbackError,HistorySaveError)
from app.services.orchestrator import run_pipeline  # 引入调度入口和SSE格式化器
from app.db.history_mapper import (get_database_status,list_history_records_by_user_id,save_history_record,update_history_feedback)
from app.rabbitmq.feedback_tasks import publish_review_submitted  # 引入点评提交事件发布器
from app.api.utils import parse_tag_list  # 引入工具函数
from app.schemas.dto.history_dto import UpsertHistoryRequest

router = APIRouter()  # 创建路由实例


@router.post("/suggest", response_model=ApiResponse[SuggestApiData])  # 定义建议生成接口
async def suggest(  # 定义支持表单上传的建议接口
    form: SuggestFormParams = Depends(),
) -> ApiResponse[SuggestApiData]:  # 返回建议响应
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
        input_data = PhotoStyleInputData(
            style=payload.style,
            location=payload.location,
            time=payload.time,
            weather=payload.weather,
            face_tags=payload.face_tags,
            shot_tags=payload.shot_tags,
            pose_tags=payload.pose_tags,
            extra_tags=[],
        )
        output_data = PhotoStyleOutputData.model_validate(result.model_dump())

        history_record = HistoryUserRecord(
            user_id=form.user_id,
            input_data=input_data,
            output_data=output_data,
            makeup_rating=0,
            outfit_rating=0,
            pose_rating=0,
            feedback_comment=None,
            reviewed=False,
        )
        history = save_history_record(history_record)
    except Exception as exc:
        logger.exception("suggest.history.save_failed")
        raise HistorySaveError(hint=str(exc)) from exc
    
    return ApiResponse[SuggestApiData](
        message="建议生成成功",
        data=SuggestApiData(**{**result.model_dump(), "history": history}),
    )


@router.get("/db/status", response_model=ApiResponse[DatabaseStatusResponse])  # 定义数据库状态接口
async def database_status() -> ApiResponse[DatabaseStatusResponse]:  # 返回数据库状态
    status = get_database_status()  # 获取数据库连接信息
    return ApiResponse[DatabaseStatusResponse](
        message="数据库状态查询成功",
        data=DatabaseStatusResponse(**status),
    )


@router.post("/history", response_model=ApiResponse[None])  # 定义历史记录保存接口
async def create_history(record: HistoryRecord) -> ApiResponse[None]:  # 接收历史记录并保存
    save_history_record(record)  # 将记录写入存储
    return ApiResponse[None](message="历史记录保存成功")


@router.get("/history", response_model=ApiResponse[HistoryListResponse])  # 定义历史记录查询接口
async def get_history(user_id: int | None = None) -> ApiResponse[HistoryListResponse]:  # 获取历史记录列表，支持按用户ID筛选
    items = list_history_records_by_user_id(user_id=user_id)  # 按用户ID筛选历史记录
    return ApiResponse[HistoryListResponse](
        message="历史记录查询成功",
        data=HistoryListResponse(items=items),
    )


@router.post("/history/{history_id}/feedback", response_model=ApiResponse[None])
async def update_history(history_id: int, payload: FeedbackUpdateRequest) -> ApiResponse[None]:
    update_history_feedback(
        UpsertHistoryRequest(
            id=history_id,
            makeup_rating=payload.makeup_rating,
            outfit_rating=payload.outfit_rating,
            pose_rating=payload.pose_rating,
            feedback_comment=payload.feedback_comment,
        )
    )
    
    logger.info("feedback.update.publishing history_id=%s", history_id)  # 记录开始发布反馈更新事件
    try:
        publish_review_submitted(history_id)  # 将 RAG 写入和用户画像更新交给 RabbitMQ 消费者异步执行
        logger.info("feedback.update.published history_id=%s", history_id)  # 记录成功发布事件
    except Exception as exc:
        logger.exception("feedback.update.publish_failed history_id=%s, error=%s", history_id, str(exc))
        raise FeedbackError(hint=f"发布反馈更新事件失败: {exc}") from exc
    return ApiResponse[None](message="点评保存成功")