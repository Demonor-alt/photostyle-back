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

_RABBITMQ_URL = os.getenv("RABBITMQ_URL")  # RabbitMQ连接URL
_FEEDBACK_QUEUE = os.getenv("RABBITMQ_FEEDBACK_QUEUE")  # 反馈队列名称


def _open_connection() -> pika.BlockingConnection:  # 定义打开RabbitMQ连接的内部函数，返回阻塞连接对象
    params = pika.URLParameters(_RABBITMQ_URL)  # 解析RabbitMQ URL参数
    params.heartbeat = int(os.getenv("RABBITMQ_HEARTBEAT", "600"))  # 设置心跳间隔，默认600秒，避免长耗时向量写入期间连接被关闭
    params.blocked_connection_timeout = int(os.getenv("RABBITMQ_BLOCKED_TIMEOUT", "300"))  # 设置连接阻塞超时时间，默认300秒
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
    logger.debug("消息编码完成:feedback.publish.message_encoded history_id=%s size=%s bytes", history_id, len(body))
    
    connection = _open_connection()  # 打开RabbitMQ连接
    logger.info("RabbitMQ连接成功:feedback.publish.connected history_id=%s", history_id)
    
    try:  # 尝试执行消息发布操作
        channel = connection.channel()  # 创建通道
        logger.info("通道创建成功:feedback.publish.channel_created history_id=%s", history_id)
        
        _declare_feedback_queue(channel)  # 声明反馈队列
        logger.info("队列声明成功:feedback.publish.queue_declared history_id=%s", history_id)
        
        channel.basic_publish(  # 发布消息到队列
            exchange="",  # 使用默认交换机
            routing_key=_FEEDBACK_QUEUE,  # 路由键为队列名称
            body=body,  # 消息体
            properties=pika.BasicProperties(  # 设置消息属性
                delivery_mode=pika.DeliveryMode.Persistent,  # 设置消息为持久化模式
                content_type="application/json",  # 设置内容类型为JSON
            ),
        )
        logger.info("消息发布成功：feedback.task.published history_id=%s queue=%s", history_id, _FEEDBACK_QUEUE)
    except Exception as exc:  # 捕获发布过程中的异常
        logger.exception("feedback.publish.failed history_id=%s error=%s", history_id, str(exc))
        raise  # 重新抛出异常
    finally:  # 无论是否发生异常，都执行以下代码
        connection.close()  # 关闭连接
        logger.info("连接关闭成功:feedback.publish.connection_closed history_id=%s", history_id)


def handle_feedback_updated(history_id: int) -> None:  # 定义处理反馈更新事件的函数，接收历史记录ID参数
    current_history = get_history_record(history_id)  # 获取历史记录信息
    user_id = int(current_history["user_id"])  # 从历史记录中提取用户ID并转换为整数
    embedding_payload = upsert_photo_style_embedding(history_id, user_id)  # 保存向量到知识库中
    logger.info(" 向量保存成功：feedback.embedding.saved=%s", embedding_payload["metadata"])


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
            if ch.is_open:
                ch.basic_ack(delivery_tag=method.delivery_tag)  # 确认消息处理成功
            else:
                logger.warning("feedback.task.ack_skipped_channel_closed body=%s", body.decode("utf-8", errors="replace"))
        except AMQPError:
            logger.exception("feedback.task.amqp_error body=%s", body.decode("utf-8", errors="replace"))
            raise
        except Exception:  # 捕获业务处理异常
            logger.exception("feedback.task.failed body=%s", body.decode("utf-8", errors="replace"))
            if ch.is_open:
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # 拒绝消息且不重新入队
            else:
                logger.warning("feedback.task.nack_skipped_channel_closed body=%s", body.decode("utf-8", errors="replace"))

    channel.basic_consume(queue=_FEEDBACK_QUEUE, on_message_callback=on_message)  # 开始消费队列消息
    logger.info("消费者启动：feedback.consumer.started queue=%s", _FEEDBACK_QUEUE)
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