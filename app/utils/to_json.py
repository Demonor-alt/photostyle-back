"""将Pydantic模型转换为JSON可序列化的格式"""  # 模块说明：提供递归 JSON 兼容转换工具。
from datetime import date, datetime  # 引入日期类型，用于转换数据库时间字段。
from enum import Enum  # 引入枚举类型，用于转换可能出现的枚举值。
from typing import Any  # 引入任意类型标注，便于工具函数接收不同对象。


def to_jsonable(value: Any) -> Any:  # 将任意对象递归转换为 JSON 可序列化结构。
    if hasattr(value, "model_dump"):  # 如果对象是 Pydantic 模型。
        return to_jsonable(value.model_dump(mode="json", by_alias=True))  # 先用 Pydantic JSON 模式导出，再递归处理嵌套值。
    if isinstance(value, dict):  # 如果对象是字典。
        return {str(key): to_jsonable(item) for key, item in value.items()}  # 将键转成字符串，并递归转换每个值。
    if isinstance(value, (list, tuple, set)):  # 如果对象是列表、元组或集合。
        return [to_jsonable(item) for item in value]  # 递归转换每个元素并统一输出列表。
    if isinstance(value, (datetime, date)):  # 如果对象是日期或时间。
        return value.isoformat()  # 转换为 ISO 字符串，避免 JSON 序列化失败。
    if isinstance(value, Enum):  # 如果对象是枚举值。
        return to_jsonable(value.value)  # 使用枚举原始值继续递归转换。
    return value  # 基础类型直接返回。
