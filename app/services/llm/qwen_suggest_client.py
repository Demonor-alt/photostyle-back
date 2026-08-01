import json  # 引入json用于组织和解析Qwen建议返回内容
from app.utils.runtime import logger
import os  # 引入os用于读取环境变量中的API密钥

from dashscope import Generation  # 引入DashScope生成接口
import dashscope  # 引入DashScope配置对象
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException

from app.schemas.llm import SuggestRequest, SuggestResponse  # 引入请求响应模型
from app.services.llm.qwen_client import get_api_key, get_qwen_response_message
from app.config.constants import QWEN_BASE_MODEL # 引入基础模型名称

dashscope.base_http_api_url = os.getenv("DASHSCOPE_API_URL")  # 配置百炼API地址
suggest_response_parser = PydanticOutputParser(pydantic_object=SuggestResponse)


# 统一调用 Qwen 生成拍照穿搭建议，避免业务层直接依赖 SDK 细节

def generate_suggestion(payload: SuggestRequest, user_face_analysis: dict | None = None) -> SuggestResponse:  # 构建最终建议结果
    # 优先使用数据库里的 face_analysis；如果请求里已经带了，也作为兜底补充
    face_analysis = user_face_analysis or payload.face_analysis or {}  # 统一人脸分析数据来源

    messages = [  # 组织给Qwen的消息
        {"role": "system", "content": """你是一个专业的拍照穿搭与姿势建议助手。
        你的输出包含五个字段：reason、outfit、makeup、poses、summary。
        核心要求：outfit、makeup、poses 三者必须构成一个协调统一的整体造型方案。它们不是各自独立的建议列表，而是为同一张照片设计的配套组合——穿搭的风格决定妆容的色调，妆容的气质决定姿势的情绪，三者互相支撑、缺一不可。
        具体要求：
        - outfit：穿搭建议列表，每一件单品的选择都要考虑与妆容和姿势的配合
        - makeup：妆容建议列表，色调、风格必须与穿搭统一（如穿搭偏冷色则妆容也偏冷调）
        - poses：姿势建议列表，动作要能展现这套穿搭的亮点，同时与妆容气质匹配
        - reason：解释为什么这三者这样搭配是协调的
        - summary：整体总结，描述最终画面效果
        请严格按格式说明输出JSON，不要输出任何解释、代码块、Markdown或多余文本。"""
        },
        {"role": "user", "content": json.dumps({
            "username": payload.username,
            "style": payload.style,
            "location": payload.location,
            "time": payload.time,
            "weather": payload.weather,
            "face_tags": payload.face_tags,
            "shot_tags": payload.shot_tags,
            "pose_tags": payload.pose_tags,
            "extra_tags": payload.extra_tags,
            "face_analysis": face_analysis,
            "format_instructions": suggest_response_parser.get_format_instructions(),
        }, ensure_ascii=False)},
    ]
    logger.info("qwen_suggest_client request=%s", json.dumps({"payload": payload.model_dump(), "face_analysis": face_analysis, "messages": messages}, ensure_ascii=False, default=str))
    response = Generation.call(
        api_key=get_api_key(),
        model=QWEN_BASE_MODEL,
        messages=messages,
        result_format="message",
        enable_thinking=True,
    )
    message = get_qwen_response_message(response)
    if message is None:
        raise ValueError("Qwen 建议生成调用失败")
    raw_text = message.content
    logger.info("qwen_suggest_client response_raw=%s", raw_text)
    try:
        result = suggest_response_parser.parse(raw_text)
    except OutputParserException as exc:
        raise ValueError("Qwen 返回内容无法映射为 SuggestResponse") from exc
    logger.info("qwen_suggest_client response_parsed=%s", result.model_dump())
    return result  # 响应对象结束
