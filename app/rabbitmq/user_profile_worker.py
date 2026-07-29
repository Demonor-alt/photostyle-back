"""UserProfile Consumer worker 启动入口。"""
from app.rabbitmq.user_profile_tasks import consume_user_profile_tasks


if __name__ == "__main__":
    consume_user_profile_tasks()
