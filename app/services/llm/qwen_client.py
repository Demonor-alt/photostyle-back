import os
from typing import Any

from app.utils.runtime import logger

api_key = os.getenv("DASHSCOPE_API_KEY")  # 读取DashScope密钥


def get_api_key() -> str:
    if not api_key:  # 如果没有配置密钥
        raise ValueError("DASHSCOPE_API_KEY 未配置，无法调用 Qwen 图片分析接口")  # 直接暴露配置问题
    return api_key


# 判断模型返回的状态码
def get_qwen_response_message(response: Any) -> Any | None:
    if response.status_code == 200:
        return response.output.choices[0].message

    log_payload = {"status_code": response.status_code}
    if hasattr(response, "code"):
        log_payload["code"] = response.code
    if hasattr(response, "message"):
        log_payload["message"] = response.message
    logger.error("qwen response error=%s", log_payload)
    return None

