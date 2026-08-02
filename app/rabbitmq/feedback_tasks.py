"""反馈点评 RabbitMQ 事件发布与公共声明模块。"""  # 发布端
from __future__ import annotations  # 启用延迟类型注解，避免运行期解析不必要的类型。

import json  # 导入 JSON 模块，用于序列化 RabbitMQ 消息体。
import os  # 导入 os 模块，用于读取 RabbitMQ 相关环境变量。
import time  # 导入 time 模块，用于生成事件创建时间戳。
from typing import Any  # 导入 Any 类型，用于标注 pika 通道对象。

import pika  # 导入 pika 客户端，用于连接 RabbitMQ 并发布消息。

from app.utils.runtime import logger  # 导入统一日志器，用于记录发布链路日志。

_RABBITMQ_URL = os.getenv("RABBITMQ_URL")  # 读取 RabbitMQ 连接 URL。
_REVIEW_SUBMITTED_EXCHANGE = os.getenv("RABBITMQ_REVIEW_SUBMITTED_EXCHANGE")  # 读取点评提交事件交换机名称。
_REVIEW_SUBMITTED_ROUTING_KEY = os.getenv("RABBITMQ_REVIEW_SUBMITTED_ROUTING_KEY")  # 读取点评提交事件路由键。


def open_connection() -> pika.BlockingConnection:  # 定义打开 RabbitMQ 连接的公共函数，供发布者和消费者复用。
    params = pika.URLParameters(_RABBITMQ_URL)  # 将 RabbitMQ URL 解析为 pika 连接参数。
    params.heartbeat = int(os.getenv("RABBITMQ_HEARTBEAT", "600"))  # 设置心跳间隔，默认 600 秒，避免长耗时任务导致连接被关闭。
    params.blocked_connection_timeout = int(os.getenv("RABBITMQ_BLOCKED_TIMEOUT", "300"))  # 设置阻塞连接超时时间，默认 300 秒。
    return pika.BlockingConnection(params)  # 创建并返回阻塞式 RabbitMQ 连接。


def declare_review_submitted_exchange(channel: Any) -> None:  # 定义声明点评提交交换机的公共函数。
    channel.exchange_declare(exchange=_REVIEW_SUBMITTED_EXCHANGE, exchange_type="fanout", durable=True)  # 声明持久化 fanout 交换机，让同一事件广播到多个消费者队列。


def declare_review_submitted_queue(channel: Any, queue_name: str) -> None:  # 定义声明并绑定点评提交队列的公共函数。
    declare_review_submitted_exchange(channel)  # 确保点评提交交换机已经存在。
    dead_letter_exchange = f"{queue_name}.dlx"  # 为当前业务队列创建独立死信交换机，避免不同消费者失败消息混在一起。
    dead_letter_queue = f"{queue_name}.dlq"  # 为当前业务队列创建独立死信队列。
    dead_letter_routing_key = f"{queue_name}.dead"  # 使用稳定路由键将死信消息投递到对应 DLQ。
    channel.exchange_declare(exchange=dead_letter_exchange, exchange_type="direct", durable=True)  # 声明持久化死信交换机。
    channel.queue_declare(queue=dead_letter_queue, durable=True)  # 声明持久化死信队列，保存处理失败且不重新入队的消息。
    channel.queue_bind(exchange=dead_letter_exchange, queue=dead_letter_queue, routing_key=dead_letter_routing_key)  # 将死信队列绑定到死信交换机。
    channel.queue_declare(
        queue=queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": dead_letter_exchange,
            "x-dead-letter-routing-key": dead_letter_routing_key,
        },
    )  # 声明持久化业务队列，并配置失败消息进入对应 DLQ。
    channel.queue_bind(exchange=_REVIEW_SUBMITTED_EXCHANGE, queue=queue_name, routing_key=_REVIEW_SUBMITTED_ROUTING_KEY)  # 将队列绑定到交换机，接收 ReviewSubmitted 广播事件。


def publish_review_submitted(history_id: int) -> None:  # 定义发布点评提交消息的公共函数，接收历史记录 ID。
    message = {  # 创建 ReviewSubmitted 事件消息字典。
        "history_id": history_id,  # 写入历史记录 ID，供消费者查询完整点评数据。
        "event": "ReviewSubmitted",  # 写入事件名称，表达用户已经提交点评。告诉消费者"这是什么业务事件"
        "created_at": int(time.time()),  # 写入事件创建时间戳，便于排查消息延迟。
    }  # 消息字典创建结束。
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")  # 将消息字典序列化为 UTF-8 JSON 字节。
    logger.debug("review_submitted.publish.message_encoded history_id=%s size=%s bytes", history_id, len(body))  # 记录消息编码完成日志。
    
    
    #TODO 每次发布都新建连接,在低频场景没问题，高频场景需要连接池
    connection = open_connection()  # 打开 RabbitMQ 连接。
    logger.info("review_submitted.publish.connected history_id=%s", history_id)  # 记录 RabbitMQ 连接成功日志。
    try:  # 开始尝试发布消息。
        channel = connection.channel()  # 创建 RabbitMQ 通道。
        logger.info("review_submitted.publish.channel_created history_id=%s", history_id)  # 记录通道创建成功日志。
        declare_review_submitted_exchange(channel)  # 声明点评提交交换机，确保发布目标存在。
        logger.info("review_submitted.publish.exchange_declared history_id=%s exchange=%s", history_id, _REVIEW_SUBMITTED_EXCHANGE)  # 记录交换机声明成功日志。
        channel.basic_publish(  # 发布 ReviewSubmitted 消息到交换机。
            exchange=_REVIEW_SUBMITTED_EXCHANGE,  # 指定点评提交 fanout 交换机。
            routing_key=_REVIEW_SUBMITTED_ROUTING_KEY,  # 指定路由键，fanout 下仅用于保持语义清晰。
            body=body,  # 指定消息体字节。
            properties=pika.BasicProperties(  # 设置消息属性。
                delivery_mode=pika.DeliveryMode.Persistent,  # 设置消息持久化，降低 RabbitMQ 重启导致的消息丢失风险。
                content_type="application/json",  # 设置消息内容类型为 JSON。
                type="ReviewSubmitted",  # 设置消息类型为 ReviewSubmitted。AMQP(高级消息队列协议) 消息属性
            ),  # 消息属性设置结束。
        )  # 消息发布调用结束。
        logger.info("review_submitted.published history_id=%s exchange=%s", history_id, _REVIEW_SUBMITTED_EXCHANGE)  # 记录消息发布成功日志。
    except Exception as exc:  # 捕获发布过程中出现的任意异常。
        logger.exception("review_submitted.publish.failed history_id=%s error=%s", history_id, str(exc))  # 记录发布失败日志。
        raise  # 重新抛出异常，让接口层返回明确错误。
    finally:  # 无论发布成功还是失败都执行清理。
        connection.close()  # 关闭 RabbitMQ 连接。
        logger.info("review_submitted.publish.connection_closed history_id=%s", history_id)  # 记录连接关闭日志。


def publish_feedback_updated(history_id: int) -> None:  # 保留旧函数名，避免现有调用方需要大范围改动。
    publish_review_submitted(history_id)  # 将旧的 feedback updated 发布行为委托给新的 ReviewSubmitted 事件。
