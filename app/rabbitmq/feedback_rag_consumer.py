"""反馈点评 RAG 消费者模块。"""  # 模块说明：负责消费用户点评提交事件并写入 RAG 向量库。
from __future__ import annotations  # 启用延迟类型注解，避免运行期解析不必要的类型。

import json  # 导入 JSON 模块，用于解析 RabbitMQ 消息体。
import os  # 导入 os 模块，用于读取环境变量配置。
from typing import Any  # 导入 Any 类型，用于标注 pika 回调参数。

import pika  # 导入 pika 客户端，用于连接和消费 RabbitMQ。
from pika.exceptions import AMQPError  # 导入 AMQPError，用于区分 RabbitMQ 协议异常。

from app.db.history_mapper import get_history_record_by_history_id  # 导入历史记录查询方法，用于获取当前点评所属用户。
from app.rag.vector_writing import upsert_photo_style_embedding  # 导入向量写入方法，用于更新 RAG 知识库。
from app.rabbitmq.feedback_tasks import declare_review_submitted_queue, open_connection  # 导入 RabbitMQ 公共连接与声明方法。
from app.utils.runtime import logger  # 导入统一日志器，用于记录消费过程。

_RAG_QUEUE = os.getenv("RABBITMQ_FEEDBACK_RAG_QUEUE")  # 读取 RAG 队列名，兼容旧反馈队列配置。


def handle_review_submitted_for_rag(history_id: int) -> None:  # 定义 RAG 事件处理函数，参数为历史记录 ID。
    current_history = get_history_record_by_history_id(history_id)  # 根据历史记录 ID 查询当前历史记录。
    user_id = int(current_history.user_id)  # 从历史记录中读取用户 ID 并转为整数。
    embedding_payload = upsert_photo_style_embedding(history_id, user_id)  # 将当前点评相关内容写入或更新到向量库。
    logger.info("feedback.rag.embedding.saved history_id=%s metadata=%s", history_id, embedding_payload.metadata)  # 读取 Pydantic 载荷属性并记录 RAG 写入成功日志。


def consume_feedback_rag_tasks() -> None:  # 定义 RAG 消费者启动函数，用于持续监听 RAG 队列。
    connection = open_connection()  # 打开 RabbitMQ 连接。
    channel = connection.channel()  # 基于连接创建 RabbitMQ 通道。
    declare_review_submitted_queue(channel, _RAG_QUEUE)  # 声明并绑定 RAG 队列到点评提交交换机。
    channel.basic_qos(prefetch_count=1)  # 设置每次只预取一条消息，避免单个消费者并发处理过多任务。

    def on_message(ch: Any, method: Any, properties: Any, body: bytes) -> None:  # 定义 RabbitMQ 消息回调函数。
        try:  # 开始尝试处理消息。
            payload = json.loads(body.decode("utf-8"))  # 将消息体从 UTF-8 字节解析为 JSON 字典。
            history_id = int(payload["history_id"])  # 从消息中读取历史记录 ID 并转为整数。
            handle_review_submitted_for_rag(history_id)  # 调用 RAG 处理函数写入向量库。
            if ch.is_open:  # 判断通道是否仍然打开。
                ch.basic_ack(delivery_tag=method.delivery_tag)  # 通道打开时确认消息处理成功。
            else:  # 通道已经关闭时进入兜底分支。
                logger.warning("feedback.rag.ack_skipped_channel_closed body=%s", body.decode("utf-8", errors="replace"))  # 记录无法确认消息的警告。
        except AMQPError:  # 捕获 RabbitMQ 协议层异常。
            logger.exception("feedback.rag.amqp_error body=%s", body.decode("utf-8", errors="replace"))  # 记录 AMQP 异常详情。
            raise  # 重新抛出 AMQP 异常，交给外层连接逻辑处理。
        except Exception:  # 捕获业务处理异常。
            logger.exception("feedback.rag.failed body=%s", body.decode("utf-8", errors="replace"))  # 记录业务处理失败日志。
            if ch.is_open:  # 判断通道是否仍然打开。
                ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)  # 拒绝失败消息且不重新入队，避免无限重试。
            else:  # 通道已经关闭时进入兜底分支。
                logger.warning("feedback.rag.nack_skipped_channel_closed body=%s", body.decode("utf-8", errors="replace"))  # 记录无法拒绝消息的警告。

    channel.basic_consume(queue=_RAG_QUEUE, on_message_callback=on_message)  # 注册 RAG 队列的消费回调。
    logger.info("feedback.rag.consumer.started queue=%s", _RAG_QUEUE)  # 记录 RAG 消费者启动日志。
    try:  # 开始启动持续消费。
        channel.start_consuming()  # 阻塞式消费 RabbitMQ 消息。
    except KeyboardInterrupt:  # 捕获手动停止信号。
        logger.info("feedback.rag.consumer.stopped")  # 记录消费者被手动停止。
    except AMQPError:  # 捕获 RabbitMQ 协议异常。
        logger.exception("feedback.rag.consumer.amqp_error")  # 记录消费者 AMQP 异常。
        raise  # 重新抛出异常，便于进程层感知失败。
    finally:  # 无论正常停止还是异常退出都执行清理。
        if connection.is_open:  # 判断连接是否仍然打开。
            connection.close()  # 关闭 RabbitMQ 连接，释放资源。
