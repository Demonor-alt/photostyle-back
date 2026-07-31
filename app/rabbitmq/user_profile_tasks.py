"""UserProfile Consumer：消费点评提交事件并更新用户画像。"""
from __future__ import annotations

import json
import os
from typing import Any

import pika
from pika.exceptions import AMQPError
from sqlalchemy.exc import IntegrityError

from app.db.database import SessionLocal, init_db
from app.db.history_mapper import get_history_record_by_history_id
from app.db.models.processed_event import ProcessedEvent
from app.services.llm.qwen_user_profile_analysis_client import analyze_user_preference
from app.services.user_profile_update_service import update_user_profile
from app.utils.runtime import logger

# UserProfile Consumer 独立监听 ReviewSubmitted exchange，不修改已有 RAG Consumer。
_EXCHANGE_NAME = os.getenv("RABBITMQ_REVIEW_EXCHANGE", "ReviewSubmitted")
_QUEUE_NAME = os.getenv("RABBITMQ_USER_PROFILE_QUEUE", "user_profile_queue")
_ROUTING_KEY = os.getenv("RABBITMQ_REVIEW_ROUTING_KEY", "review.submitted")
_RABBITMQ_URL = os.getenv("RABBITMQ_URL")
_CONSUMER_NAME = "user_profile_consumer"


def _open_connection() -> pika.BlockingConnection:
    """创建 RabbitMQ 阻塞连接。"""
    if not _RABBITMQ_URL:
        raise RuntimeError("未配置 RABBITMQ_URL，无法启动 UserProfile Consumer")
    params = pika.URLParameters(_RABBITMQ_URL)
    params.heartbeat = int(os.getenv("RABBITMQ_HEARTBEAT", "600"))
    params.blocked_connection_timeout = int(os.getenv("RABBITMQ_BLOCKED_TIMEOUT", "300"))
    return pika.BlockingConnection(params)


def _declare_review_queue(channel: Any) -> None:
    """声明交换机、队列和绑定关系。"""
    channel.exchange_declare(exchange=_EXCHANGE_NAME, exchange_type="direct", durable=True)
    channel.queue_declare(queue=_QUEUE_NAME, durable=True)
    channel.queue_bind(exchange=_EXCHANGE_NAME, queue=_QUEUE_NAME, routing_key=_ROUTING_KEY)


def _event_processed(event_id: str) -> bool:
    """检查事件是否已经处理过。"""
    db = SessionLocal()
    try:
        exists = db.query(ProcessedEvent).filter(ProcessedEvent.event_id == event_id).first() is not None
        logger.info("user_profile.event.idempotency_checked event_id=%s processed=%s", event_id, exists)
        return exists
    finally:
        db.close()


def _mark_event_processed(event_id: str, event_type: str) -> None:
    """记录事件已处理，用于消费幂等。"""
    db = SessionLocal()
    try:
        db.add(ProcessedEvent(event_id=event_id, event_type=event_type, consumer=_CONSUMER_NAME))
        db.commit()
        logger.info("user_profile.event.marked_processed event_id=%s event_type=%s", event_id, event_type)
    except IntegrityError:
        db.rollback()
        logger.info("user_profile.event.mark_processed_duplicate event_id=%s", event_id)
    except Exception:
        db.rollback()
        logger.exception("user_profile.event.mark_processed_failed event_id=%s", event_id)
        raise
    finally:
        db.close()


def _require_event_id(payload: dict[str, Any]) -> str:
    """提取 event_id；没有 event_id 时拒绝消息，避免无法幂等。"""
    event_id = str(payload.get("event_id", "")).strip()
    if not event_id:
        raise ValueError("消息缺少 event_id，无法进行幂等消费")
    return event_id


def _build_context(payload: dict[str, Any]) -> dict[str, Any]:
    """从消息或历史记录中构造偏好分析与画像更新上下文。"""
    history = None
    history_id = payload.get("history_id")
    if history_id is not None:
        history = get_history_record_by_history_id(int(history_id))

    source = history or payload
    user_id = int(payload.get("user_id") or source["user_id"])
    comment = str(payload.get("comment") or source.get("feedback_comment") or "").strip()
    history_scores = payload.get("history_scores") or {
        "makeup_rating": source.get("makeup_rating", 0),
        "outfit_rating": source.get("outfit_rating", 0),
        "pose_rating": source.get("pose_rating", 0),
    }
    input_data = payload.get("input_data") or source.get("input_data") or {}
    output_data = payload.get("output_data") or source.get("output_data") or {}
    history_profile = payload.get("history_profile") or {}
    return {
        "history_id": history_id,
        "user_id": user_id,
        "comment": comment,
        "history_scores": history_scores,
        "history_profile": history_profile,
        "input_data": input_data,
        "output_data": output_data,
    }


def handle_review_submitted(payload: dict[str, Any]) -> dict[str, Any]:
    """处理单条点评提交事件：分析偏好并更新用户画像。"""
    event_id = _require_event_id(payload)
    event_type = str(payload.get("event", payload.get("event_type", "review.submitted")))
    if _event_processed(event_id):
        logger.info("user_profile.event.skipped_duplicate event_id=%s", event_id)
        return {"event_id": event_id, "status": "duplicate"}

    context = _build_context(payload)
    logger.info("user_profile.consumer.analysis_started event_id=%s user_id=%s", event_id, context["user_id"])
    logger.info("user_profile.consumer.milvus_query_started event_id=%s comment=%s", event_id, context["comment"])
    analysis = analyze_user_preference(
        user_id=context["user_id"],
        comment=context["comment"],
        history_scores=context["history_scores"],
        history_profile=context["history_profile"],
    )
    logger.info("user_profile.consumer.llm_result event_id=%s result=%s", event_id, json.dumps(analysis, ensure_ascii=False, default=str))

    logger.info("user_profile.consumer.profile_update_started event_id=%s user_id=%s", event_id, context["user_id"])
    updated_profile = update_user_profile(
        user_id=context["user_id"],
        axis_updates=analysis.get("axis_updates"),
        history_scores=context["history_scores"],
        history_profile=context["history_profile"],
        input_data=context["input_data"],
        output_data=context["output_data"],
        avoid_patterns=analysis.get("avoid_patterns"),
        success_patterns=analysis.get("success_patterns"),
    )
    logger.info("user_profile.consumer.profile_updated event_id=%s profile=%s", event_id, json.dumps(updated_profile, ensure_ascii=False, default=str))
    _mark_event_processed(event_id, event_type)
    return {"event_id": event_id, "status": "processed", "profile": updated_profile}


def consume_user_profile_tasks() -> None:
    """启动 UserProfile Consumer，持续监听 user_profile_queue。"""
    init_db()
    connection = _open_connection()
    channel = connection.channel()
    _declare_review_queue(channel)
    channel.basic_qos(prefetch_count=1)

    def on_message(ch: Any, method: Any, properties: Any, body: bytes) -> None:
        body_text = body.decode("utf-8", errors="replace")
        logger.info("user_profile.consumer.message_received body=%s", body_text)
        try:
            payload = json.loads(body_text)
            if not isinstance(payload, dict):
                raise ValueError("消息体必须是 JSON 对象")
            handle_review_submitted(payload)
            if ch.is_open:
                ch.basic_ack(delivery_tag=method.delivery_tag)
                logger.info("user_profile.consumer.ack_success delivery_tag=%s", method.delivery_tag)
        except AMQPError:
            logger.exception("user_profile.consumer.amqp_error body=%s", body_text)
            raise
        except Exception:
            logger.exception("user_profile.consumer.failed_nack body=%s", body_text)
            if ch.is_open:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                logger.info("user_profile.consumer.nack_success delivery_tag=%s", method.delivery_tag)

    channel.basic_consume(queue=_QUEUE_NAME, on_message_callback=on_message)
    logger.info(
        "user_profile.consumer.started exchange=%s queue=%s routing_key=%s",
        _EXCHANGE_NAME,
        _QUEUE_NAME,
        _ROUTING_KEY,
    )
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("user_profile.consumer.stopped")
    except AMQPError:
        logger.exception("user_profile.consumer.amqp_error")
        raise
    finally:
        if connection.is_open:
            connection.close()
