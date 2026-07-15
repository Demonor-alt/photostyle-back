import json  # 引入JSON模块用于序列化与反序列化

from app.db.connection import create_mysql_connection, get_mysql_config  # 引入MySQL连接工厂与配置读取
from app.db.mysql_repo import MySQLHistoryRepository  # 引入MySQL仓储


def _get_repository():  # 获取可用仓储
    connection = create_mysql_connection()  # 创建MySQL连接
    return MySQLHistoryRepository(connection)  # 返回MySQL仓储实例


def get_database_status() -> dict:  # 获取数据库连接状态
    config = get_mysql_config()  # 读取数据库配置
    connection = create_mysql_connection()  # 尝试创建连接
    if connection is None:  # 如果连接失败
        raise ConnectionError("MySQL数据库连接失败，请检查环境变量和数据库服务是否可用")  # 直接抛出异常暴露问题
    connection.close()  # 关闭连接，避免泄漏
    return {"enabled": True, "database": config["database"], "host": config["host"], "port": config["port"], "user": config["user"]}  # 返回可用状态


def save_history_record(record: dict) -> None:  # 保存历史记录
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    repository.save({  # 保存到MySQL
        "user_id": record["user_id"],  # 用户ID
        "input_data": json.dumps(record["input_data"], ensure_ascii=False),  # 序列化输入
        "output_data": json.dumps(record["output_data"], ensure_ascii=False),  # 序列化输出
        "liked": record.get("liked", False),  # 保存喜欢状态
        "shot_success": record.get("shot_success", False),  # 保存出片状态
    })


def update_history_feedback(history_id: int, liked: bool, shot_success: bool) -> None:  # 更新历史记录反馈
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    repository.update_feedback(history_id, liked, shot_success)  # 更新反馈信息


def list_history_records() -> list:  # 查询历史记录
    repository = _get_repository()  # 获取仓储
    repository.ensure_schema()  # 确保表结构存在
    rows = repository.list()  # 查询结果
    normalized = []  # 初始化标准化列表
    for row in rows:  # 遍历数据库结果
        if isinstance(row, dict):
            data = row
        elif hasattr(row, "keys"):
            data = dict(row)
        else:
            data = {
                "id": row[0],
                "user_id": row[1],
                "input_data": row[2],
                "output_data": row[3],
                "liked": row[4],
                "shot_success": row[5],
                "created_at": row[6],
            }
        normalized.append({  # 组装返回结构
            "id": data["id"],  # 记录ID
            "user_id": data["user_id"],  # 用户ID
            "input_data": data["input_data"],  # 输入数据
            "output_data": data["output_data"],  # 输出数据
            "liked": bool(data["liked"]),  # 喜欢状态
            "shot_success": bool(data["shot_success"]),  # 出片状态
            "created_at": str(data["created_at"]),  # 创建时间
        })
    return normalized  # 返回标准化结果
