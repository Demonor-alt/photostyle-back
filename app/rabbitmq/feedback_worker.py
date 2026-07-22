"""反馈任务工作者入口点"""  # 模块文档字符串，描述该模块的功能
from app.rabbitmq.feedback_tasks import consume_feedback_tasks  # 从rabbitmq模块导入反馈任务消费者函数


if __name__ == "__main__":  # 当脚本作为主程序运行时执行以下代码
    consume_feedback_tasks()  # 启动反馈任务消费者，开始处理队列中的消息