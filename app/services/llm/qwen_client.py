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

