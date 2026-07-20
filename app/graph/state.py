from typing import TypedDict  # 引入TypedDict用于定义工作流状态

from app.schemas.history import SuggestRequest  # 引入请求模型


class PhotoStyleState(TypedDict, total=False):  # 定义PhotoStyle工作流状态
    request: SuggestRequest  # 原始请求对象
    parsed_input: dict  # 输入解析后的结构化信息
    image_analysis: dict  # Qwen图片分析结果
    retrieved_context: dict  # RAG检索到的上下文
    suggestion: dict  # DeepSeek生成的建议结果
    evaluation: dict  # 评价节点输出结果
