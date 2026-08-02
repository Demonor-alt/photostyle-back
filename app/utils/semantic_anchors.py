from typing import Any  # 用于表示任意类型。
from app.config.constants import AXIS_VALUE_MIN, AXIS_VALUE_MAX, AXIS_VALUE_DECIMAL_PLACES, AXIS_VALUE_DEFAULT # 引入语义轴取值
from functools import lru_cache  # 为配置读取增加缓存。
from pathlib import Path  # 处理文件路径。

import yaml  # 解析 YAML 配置。

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "scripts" / "semantic_axes.yaml"  # 语义轴配置文件路径。


#region 拿语义轴前两项举例
# config = {
#     "color_saturation": {
#         "axis_name": "color_saturation",
#         "label": "服装色彩饱和度",
#         "description": "低饱和 ←→ 高饱和。该轴只描述服装用色的鲜艳程度。\n低方向 value -1~-0.5：喜欢浅色系、低饱和、清淡颜色...\n中性 value -0.2~0.2：没有明显色彩偏好...\n高方向 value 0.5~1：喜欢鲜艳色..."
#     },
#     "accessory_level": {
#         "axis_name": "accessory_level",
#         "label": "配饰接受程度",
#         "description": "无配饰 ←→ 丰富配饰。该轴只描述耳环、项链、戒指...\n低方向 value -1~-0.5：喜欢极简...\n中性 value -0.2~0.2：可有可无...\n高方向 value 0.5~1：喜欢耳环项链..."
#     }
# }
#endregion
@lru_cache(maxsize=1)
def load_semantic_axes_config() -> dict[str, dict[str, str]]:
    """读取语义轴配置，服务逻辑只依赖配置中的 axis name。"""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"语义轴配置文件不存在: {_CONFIG_PATH}")
    parsed = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
    axes = parsed.get("semantic_axes", []) if isinstance(parsed, dict) else []
    if not isinstance(axes, list):
        raise ValueError(f"语义轴配置 semantic_axes 必须是列表: {_CONFIG_PATH}")
    config: dict[str, dict[str, str]] = {}
    for item in axes:
        axis_name = str(item.get("axis_name", "")).strip()
        if not axis_name:
            continue
        config[axis_name] = item
    if not config:
        raise ValueError(f"语义轴配置为空或格式错误: {_CONFIG_PATH}")
    return config

#region 拿语义轴前两项
#{"color_saturation", "accessory_level"}
#endregion
def get_semantic_axis_names() -> set[str]:
    """返回配置中定义的全部语义轴名称，支持未来通过 YAML 扩展。"""
    return set(load_semantic_axes_config().keys())

def clamp(value: Any, min_value: float=AXIS_VALUE_MIN, max_value: float=AXIS_VALUE_MAX, default: float = AXIS_VALUE_DEFAULT, decimal_places: int = AXIS_VALUE_DECIMAL_PLACES) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(min_value, min(number, max_value)), decimal_places)


