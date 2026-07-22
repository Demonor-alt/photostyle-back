"""基于RabbitMQ的反馈跟进任务处理模块"""  # 模块文档字符串，描述该模块的功能
from __future__ import annotations  # 允许延迟类型注解评估，提高代码兼容性

import json  # 导入JSON处理模块，用于序列化和反序列化数据
import os  # 导入操作系统接口模块，用于读取环境变量
import time  # 导入时间处理模块，用于获取时间戳
from typing import Any  # 导入类型注解模块，用于类型提示

import pika  # 导入RabbitMQ客户端库
from pika.exceptions import AMQPError  # 导入AMQP错误异常类

from app.db.history_mapper import get_history_record  # 导入历史记录查询函数
from app.db.user_mapper import get_user_profile_by_id  # 导入用户信息查询函数
from app.rag.vector_writing import upsert_photo_style_embedding  # 导入图片风格嵌入更新函数
from app.utils.runtime import logger  # 导入日志记录器

_RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")  # RabbitMQ连接URL，默认使用本地服务器
_FEEDBACK_QUEUE = os.getenv("RABBITMQ_FEEDBACK_QUEUE", "photo_style.feedback.updated")  # 反馈队列名称，默认使用指定名称


def _open_connection() -> pika.BlockingConnection:  # 定义打开RabbitMQ连接的内部函数，返回阻塞连接对象
    params = pika.URLParameters(_RABBITMQ_URL)  # 解析RabbitMQ URL参数
    params.heartbeat = int(os.getenv("RABBITMQ_HEARTBEAT", "60"))  # 设置心跳间隔，默认60秒
    params.blocked_connection_timeout = int(os.getenv("RABBITMQ_BLOCKED_TIMEOUT", "30"))  # 设置连接阻塞超时时间，默认30秒
    return pika.BlockingConnection(params)  # 创建并返回阻塞连接


def _declare_feedback_queue(channel: Any) -> None:  # 定义声明反馈队列的内部函数，接收通道参数
    channel.queue_declare(queue=_FEEDBACK_QUEUE, durable=True)  # 声明持久化队列，确保消息不丢失


def publish_feedback_updated(history_id: int) -> None:  # 定义发布反馈更新消息的公共函数，接收历史记录ID参数
    message = {  # 创建消息内容字典
        "history_id": history_id,  # 历史记录ID
        "event": "feedback.updated",  # 事件类型
        "created_at": int(time.time()),  # 消息创建时间戳
    }
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")  # 将消息转换为JSON字符串并编码为UTF-8字节
    connection = _open_connection()  # 打开RabbitMQ连接
    try:  # 尝试执行消息发布操作
        channel = connection.channel()  # 创建通道
        _declare_feedback_queue(channel)  # 声明反馈队列
        channel.basic_publish(  # 发布消息到队列
            exchange="",  # 使用默认交换机
            routing_key=_FEEDBACK_QUEUE,  # 路由键为队列名称
            body=body,  # 消息体
            properties=pika.BasicProperties(  # 设置消息属性
                delivery_mode=pika.DeliveryMode.Persistent,  # 设置消息为持久化模式
                content_type="application/json",  # 设置内容类型为JSON
            ),
        )
        logger.info("feedback.task.published history_id=%s queue=%s", history_id, _FEEDBACK_QUEUE)  # 记录消息发布日志
    finally:  # 无论是否发生异常，都执行以下代码
        connection.close()  # 关闭连接


def handle_feedback_updated(history_id: int) -> None:  # 定义处理反馈更新事件的函数，接收历史记录ID参数
    current_history = get_history_record(history_id)  # 获取历史记录信息
    user_id = int(current_history["user_id"])  # 从历史记录中提取用户ID并转换为整数
    user = get_user_profile_by_id(user_id)  # 根据用户ID获取用户信息
    embedding_payload = upsert_photo_style_embedding(history_id, user_id)  # 更新图片风格嵌入向量
    logger.info("feedback.embedding.saved=%s", embedding_payload["metadata"])  # 记录嵌入保存成功的日志
    if user.get("simple_analysis") is not None:  # 检查用户是否有简单分析结果
        logger.info("feedback.user.simple_analysis.ready user_id=%s", user["id"])  # 记录用户分析准备好的日志


def consume_feedback_tasks() -> None:  # 定义消费反馈任务的函数，用于持续监听队列并处理消息
    connection = _open_connection()  # 打开RabbitMQ连接
    channel = connection.channel()  # 创建通道
    _declare_feedback_queue(channel)  # 声明反馈队列
    channel.basic_qos(prefetch_count=1)  # 设置服务质量，每次只预取一条消息

    def on_message(ch: Any, method: Any, properties: Any, body: bytes) -> None:  # 定义消息处理回调函数
        try:  # 尝试处理消息
            payload = json.loads(body.decode("utf-8"))  # 解码并解析消息体为JSON
            history_id = int(payload["history_id"])  # 从消息中提取历史记录ID
            handle_feedback_updated(history_id)  # 处理反馈更新事件
            ch.basic_ack(delivery_tag=method.delivery_tag)  # 确认消息处理成功
        except Exception:  # 捕获所有异常
            logger.exception("feedback.task.failed body=%s", body.decode("utf-8", errors="replace"))  # 记录失败日志
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # 拒绝消息且不重新入队

    channel.basic_consume(queue=_FEEDBACK_QUEUE, on_message_callback=on_message)  # 开始消费队列消息
    logger.info("feedback.consumer.started queue=%s", _FEEDBACK_QUEUE)  # 记录消费者启动日志
    try:  # 尝试启动消息消费
        channel.start_consuming()  # 开始持续消费消息
    except KeyboardInterrupt:  # 捕获键盘中断异常（Ctrl+C）
        logger.info("feedback.consumer.stopped")  # 记录消费者停止日志
    except AMQPError:  # 捕获AMQP协议错误异常
        logger.exception("feedback.consumer.amqp_error")  # 记录AMQP错误日志
        raise  # 重新抛出异常
    finally:  # 无论是否发生异常，都执行以下代码
        if connection.is_open:  # 检查连接是否仍然打开
            connection.close()  # 关闭连接