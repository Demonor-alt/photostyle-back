from datetime import datetime
from pydantic import Field

from app.schemas.base import BaseSchema
from pydantic import Field, RootModel, field_validator  # 引入 Pydantic 字段、根模型和字段校验器。
from typing import Any  # 引入 Any，用于描述暂未收紧结构的动态字段值。
from app.config.constants import AXIS_VALUE_MIN, AXIS_VALUE_MAX

class SemanticAxes(RootModel[dict[str, float]]):  # 定义用户语义轴画像模型，根结构就是轴名到分数的字典。
    root: dict[str, float] = Field(default_factory=dict)  # 保存语义轴分数字典，例如 {"甜美感": 0.8}。

    @field_validator("root", mode="before")  # 在 root 字段正式校验前先执行归一化处理。
    @classmethod  # 声明为类方法，符合 Pydantic 字段校验器签名要求。
    def normalize_axes(cls, value: Any) -> dict[str, float]:  # 定义语义轴归一化逻辑，将输入整理为 dict[str, float]。
        normalized: dict[str, float] = {}  # 初始化归一化后的语义轴结果。
        for axis_name, axis_value in value.items():  # 遍历原始语义轴的轴名和值。
            try:  # 尝试将每个轴值转换为合法浮点数。
                normalized[str(axis_name)] = max(AXIS_VALUE_MIN, min(AXIS_VALUE_MAX, float(axis_value)))  # 轴名转字符串，轴值限制在 -1.0 到 1.0。
            except (TypeError, ValueError):  # 如果轴值无法转成数字，说明该项无效。
                continue  # 跳过无效语义轴，不影响其他有效字段。
        return normalized  # 返回清洗后的语义轴字典。


class UserPersona(BaseSchema):
    id: int
    user_id: int
    semantic_axes: SemanticAxes = Field(default_factory=SemanticAxes)
    created_at: datetime | None = None
    updated_at: datetime | None = None
