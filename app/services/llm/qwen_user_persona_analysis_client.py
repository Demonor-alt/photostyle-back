"""用户偏好分析服务。"""  # 模块说明：负责分析用户评论并生成偏好画像更新结果。
from __future__ import annotations  # 启用前向引用类型注解。

import json  # 用于 JSON 序列化。
import os  # 用于读取环境变量。
from typing import Any  # 用于表示任意类型。

import dashscope  # 引入 DashScope SDK。
from dashscope import Generation  # 引入文本生成能力。
from langchain_core.output_parsers import PydanticOutputParser  # 引入 Pydantic 输出解析器。

from app.services.llm.qwen_client import get_api_key, get_qwen_response_content  # 引入统一的 Qwen 鉴权和响应文本提取方法。
from app.utils.runtime import logger  # 引入统一日志器。
from app.schemas.llm import PreferenceAnalysisOutput,UserPersonaAnalysisRequest # 引入用户偏好分析输出结构。
from app.config.constants import QWEN_BASE_MODEL # 引入基础模型名称
from app.utils.semantic_anchors import clamp # 引入语义轴取值标准化方法
from app.config.constants import AXIS_VALUE_MIN, AXIS_VALUE_MAX,AXIS_VALUE_DEFAULT # 引入语义轴取值最小值和最大值

# 配置 DashScope 百炼 API 地址，保持和现有 Qwen 服务一致。  # 让 SDK 指向正确的服务地址。
dashscope.base_http_api_url = os.getenv("DASHSCOPE_API_URL")  # 设置 DashScope 基础 API 地址。


_PREFERENCE_ANALYSIS_PARSER = PydanticOutputParser(pydantic_object=PreferenceAnalysisOutput)  # 定义偏好分析结果解析器


def analyze_user_preference(  # 对单个用户评论进行偏好分析。
    payload: UserPersonaAnalysisRequest
) -> PreferenceAnalysisOutput:
    messages = [  # 组装大模型消息。
        {"role": "system", "content": """你是用户审美偏好分析服务。请根据用户评论、Milvus 语义锚点召回结果、历史画像和历史评分，
        推断用户偏好的语义轴更新。不要使用固定关键词规则，只能基于输入证据做判断。
        INPUT:
        1. 当前生成方案
        2. 用户评分
        3. 用户评论
        4. 当前用户semantic_axes
        5. Milvus召回的语义轴锚点
        请严格只输出 JSON，不要输出解释、Markdown 或代码块。"""
        f"请遵循以下格式要求：{_PREFERENCE_ANALYSIS_PARSER.get_format_instructions()}"  # LangChain解析器格式要求。
        "JSON 字段必须包含 axis_updates"  # 要求字段完整。
        f"其中 value 表示你对用户偏好的判断，范围 {AXIS_VALUE_MIN} 到 {AXIS_VALUE_MAX}，如果用户偏好没涉及当前语义轴，则value为{AXIS_VALUE_DEFAULT}，负数表示用户与语义轴的描述相反，正数表示用户与语义轴的描述一致，要有依据，不要自行融合 Milvus similarity。reason 表示判断原因，简短说明。"  # 置信度说明。
        },
        {"role": "user", "content": json.dumps({
            "input_data": payload.input_data,
            "output_data": payload.output_data,# TODO:这里要改成输出的标签，而不是整个输出数据
            "comment": payload.comment,
            "anchors": payload.anchors,
            "old_semantic_axes": payload.old_semantic_axes,
            "makeup_rating": payload.makeup_rating,
            "outfit_rating": payload.outfit_rating,
            "pose_rating": payload.pose_rating,
        }, ensure_ascii=False)},  # 用户消息。
    ]  # 消息组装结束。
    logger.info("preference.analysis.request comment=%s anchors=%s",payload.comment,payload.anchors)  # 日志记录结束。
    response = Generation.call(  # 调用 Qwen 生成接口。
        api_key=get_api_key(),  # 传入 API Key。
        model=QWEN_BASE_MODEL,  # 选择模型。
        messages=messages,  # 传入消息列表。
        result_format="message",  # 结果格式为 message。
        enable_thinking=True,  # 开启思考能力。
    )  # 请求结束。
    raw_text = get_qwen_response_content(response)  # 统一判断响应并提取 message.content 文本。
    if raw_text is None:  # 响应失败时抛出可读异常。
        raise RuntimeError(f"Qwen 偏好分析调用失败，response={response}")  # 暴露调用失败信息。
    logger.info("preference.analysis.response_raw raw=%s", raw_text)  # 记录原始响应。
    parsed = _PREFERENCE_ANALYSIS_PARSER.parse(raw_text)  # 使用LangChain解析并映射到Pydantic模型。


    axis_updates = []  # 初始化清洗后的更新列表。
    for item in parsed.axis_updates:  # 遍历每条更新。
        axis_name = str(item.axis_name).strip()  # 获取并清理轴名称。
        if not axis_name:  # 空名称忽略。
            continue  # 跳过。
        axis_updates.append(  # 追加标准化后的记录。
            item.model_copy(  # 保持 PreferenceAxisUpdateOutput 类型。
                update={  # 单条标准化记录。
                    "axis_name": axis_name,  # 标准化轴名。
                    "value": clamp(item.value),  # 标准化值域。
                    "reason": str(item.reason).strip(),  # 标准化原因文本。
                }  # 单条记录结束。
            )  # 复制结束。
        )  # 追加结束。

    return PreferenceAnalysisOutput(axis_updates=axis_updates)  # 返回分析结果。
