from typing import Any  # 用于表示任意类型。
from app.config.constants import AXIS_VALUE_MIN, AXIS_VALUE_MAX, AXIS_VALUE_DECIMAL_PLACES, AXIS_VALUE_DEFAULT # 引入语义轴取值


def clamp(value: Any, min_value: float=AXIS_VALUE_MIN, max_value: float=AXIS_VALUE_MAX, default: float = AXIS_VALUE_DEFAULT, decimal_places: int = AXIS_VALUE_DECIMAL_PLACES) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(min_value, min(number, max_value)), decimal_places)


