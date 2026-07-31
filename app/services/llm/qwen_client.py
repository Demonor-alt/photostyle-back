import os
from typing import Any

from app.utils.runtime import logger

api_key = os.getenv("DASHSCOPE_API_KEY")  # 读取DashScope密钥


def get_api_key() -> str:
    if not api_key:  # 如果没有配置密钥
        raise ValueError("DASHSCOPE_API_KEY 未配置，无法调用 Qwen 图片分析接口")  # 直接暴露配置问题
    return api_key


def _get_attr_or_item(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _message_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            text = _get_attr_or_item(item, "text")
            if text is not None:
                text_parts.append(str(text))
        return "\n".join(text_parts)
    if content is None:
        return ""
    return str(content)


# 判断模型返回的状态码，并提取 result_format="message" 下的 choices[0].message
def get_qwen_response_message(response: Any) -> Any | None:
    if response.status_code == 200:
        choices = _get_attr_or_item(_get_attr_or_item(response, "output"), "choices", [])
        if choices:
            return _get_attr_or_item(choices[0], "message")
        logger.error("qwen response choices empty response=%s", response)
        return None

    log_payload = {"status_code": response.status_code}
    if hasattr(response, "code"):
        log_payload["code"] = response.code
    if hasattr(response, "message"):
        log_payload["message"] = response.message
    logger.error("qwen response error=%s", log_payload)
    return None


# 判断模型返回的状态码，并直接提取 result_format="message" 下的 message.content 文本
def get_qwen_response_content(response: Any) -> str | None:
    message = get_qwen_response_message(response)
    if message is None:
        return None
    return _message_content_to_text(_get_attr_or_item(message, "content", ""))



#-------------------------------------- tool --------------------------------------


#region
# 情况1：正常数组
#_normalize_list(["大眼睛", "高鼻梁", "薄唇"])
# # → ["大眼睛", "高鼻梁", "薄唇"]
# # 情况2：逗号分隔的字符串
# _normalize_list("大眼睛，高鼻梁,薄唇")
# # → ["大眼睛", "高鼻梁", "薄唇"]
# 情况3：有空格或空值的脏数据
# _normalize_list(["大眼睛", " ", "", "高鼻梁"])
# → ["大眼睛", "高鼻梁"]
# 情况4：模型抽风返回了 null 或数字
# _normalize_list(None)
# → []
# _normalize_list(123)
# → []
#endregion
def normalize_list(value: object) -> list[str]:  # 将任意值规范为字符串列表
    if isinstance(value, list):  # 如果本来就是列表
        return [str(item).strip() for item in value if str(item).strip()]  # 转换并过滤空值
    if isinstance(value, str):  # 如果是字符串
        parts = [part.strip() for part in value.replace("，", ",").split(",")]  # 按中英文逗号切分
        return [part for part in parts if part]  # 过滤空项
    return []  # 其他类型直接返回空列表

#递归地把多层嵌套的枚举字典压平成 JSON 文本
def build_simple_analysis_enum_text(enums: dict[str, object]) -> str:  # 将简化分析枚举递归展开为提示词文本
    lines: list[str] = []  # 收集每一层枚举描述
    for key, value in enums.items():  # 遍历当前层级
        if isinstance(value, dict):  # 如果是子结构，继续递归展开
            child_text = build_simple_analysis_enum_text(value)  # 生成子结构文本
            lines.append(f'"{key}":{{{child_text}}}')  # 拼接当前层级
        else:  # 如果是枚举集合
            options = ",".join(f'"{item}"' for item in sorted(value))  # 排序后生成稳定输出
            lines.append(f'"{key}":[{options}]')  # 拼接枚举数组
    return ",".join(lines)  # 返回当前层级的JSON片段