"""反馈点评消费者工作进程入口。"""  # 模块说明：同时启动 RAG Consumer 和 UserProfile Consumer。
from __future__ import annotations  # 启用延迟类型注解，避免运行期解析不必要的类型。

from collections.abc import Callable  # 导入 Callable 类型，用于标注消费者启动函数。
from threading import Thread  # 导入线程类，用于在同一进程内并行运行两个阻塞消费者。

from app.rabbitmq.feedback_rag_consumer import consume_feedback_rag_tasks  # 导入 RAG 消费者启动函数。
from app.rabbitmq.feedback_user_profile_consumer import consume_feedback_user_profile_tasks  # 导入用户画像消费者启动函数。
from app.utils.runtime import logger  # 导入统一日志器，用于记录 worker 启动状态。


def _start_consumer_thread(name: str, target: Callable[[], None]) -> Thread:  # 定义启动消费者线程的内部函数。
    thread = Thread(target=target, name=name, daemon=False)  # 创建非守护线程，保证主进程等待消费者持续运行。
    thread.start()  # 启动消费者线程。
    logger.info("feedback.worker.consumer_thread_started name=%s", name)  # 记录消费者线程启动成功日志。
    return thread  # 返回线程对象，供主线程等待。


if __name__ == "__main__":  # 当脚本作为主程序运行时执行以下代码。
    rag_thread = _start_consumer_thread("feedback-rag-consumer", consume_feedback_rag_tasks)  # 启动 RAG Consumer 线程。
    user_profile_thread = _start_consumer_thread("feedback-user-profile-consumer", consume_feedback_user_profile_tasks)  # 启动 UserProfile Consumer 线程。
    rag_thread.join()  # 等待 RAG Consumer 线程结束，正常情况下会一直阻塞。
    user_profile_thread.join()  # 等待 UserProfile Consumer 线程结束，正常情况下会一直阻塞。
