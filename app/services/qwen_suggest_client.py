import json  # 引入json用于组织和解析Qwen建议返回内容
import logging  # 引入logging用于记录调用输入输出
import os  # 引入os用于读取环境变量中的API密钥

from dashscope import Generation  # 引入DashScope生成接口
import dashscope  # 引入DashScope配置对象

from app.models import SuggestRequest, SuggestResponse  # 引入请求响应模型
from app.rag.retriever import retrieve_context  # 引入RAG检索函数


dashscope.base_http_api_url = 'https://dashscope.aliyuncs.com/api/v1'  # 配置百炼API地址
logger = logging.getLogger(__name__)  # 创建模块级日志器


# 将检索到的文本列表整理成更适合提示词使用的中文段落

def _format_context_items(items: list[str], title: str) -> str:  # 将检索结果整理成中文文本
    if not items:  # 如果没有结果
        return f"{title}：暂无"  # 返回空提示
    return f"{title}：\n- " + "\n- ".join(items)  # 将列表拼接为易读文本


# 统一调用 Qwen 生成拍照穿搭建议，避免业务层直接依赖 SDK 细节

def generate_suggestion(payload: SuggestRequest, user_face_analysis: dict | None = None) -> SuggestResponse:  # 构建最终建议结果
    # 优先使用数据库里的 face_analysis；如果请求里已经带了，也作为兜底补充
    face_analysis = user_face_analysis or payload.face_analysis or {}  # 统一人脸分析数据来源
    # 用前端传来的全部选择项与人脸分析一起做RAG检索
    context = retrieve_context(payload, parsed_input={
        "style": payload.style,
        "location": payload.location,
        "time": payload.time,
        "weather": payload.weather,
        "face_tags": payload.face_tags,
        "shot_tags": payload.shot_tags,
        "pose_tags": payload.pose_tags,
        "extra_tags": payload.extra_tags,
    }, image_analysis=face_analysis)  # 根据用户输入检索知识库内容
    if not context.get("outfit") and not context.get("makeup") and not context.get("poses") and not context.get("scene_tips"):  # 如果没有任何检索结果
        raise ValueError("知识库未返回任何内容，请检查种子数据和检索条件")  # 直接暴露空结果问题

    messages = [  # 组织给Qwen的消息
        {"role": "system", "content": "你是一个专业的拍照穿搭与姿势建议助手。请严格只输出JSON，不要输出任何解释、代码块、Markdown或多余文本。JSON字段必须包括outfit、makeup、poses、summary，其中outfit、makeup、poses必须是数组，summary必须是字符串。"},
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
            "rag_context": context,
            "output_schema": {"outfit": ["string"], "makeup": ["string"], "poses": ["string"], "summary": "string"},
        }, ensure_ascii=False)},
    ]
    logger.info("qwen_suggest_client request=%s", json.dumps({"payload": payload.model_dump(), "face_analysis": face_analysis, "rag_context": context, "messages": messages}, ensure_ascii=False, default=str))
    api_key = os.getenv("DASHSCOPE_API_KEY")  # 读取百炼API Key
    if not api_key:  # 如果没有配置密钥
        raise RuntimeError("未配置 DASHSCOPE_API_KEY，无法调用 Qwen 生成建议")  # 直接暴露配置问题
    response = Generation.call(
        api_key=api_key,
        model="qwen3-max",
        messages=messages,
        result_format="message",
        enable_thinking=True,
    )
    raw_text = response.output.choices[0].message.content
    logger.info("qwen_suggest_client response_raw=%s", raw_text)
    try:
        payload_data = json.loads(raw_text)
    except Exception as exc:
        raise ValueError("Qwen 返回内容无法解析为 JSON") from exc
    outfit = payload_data.get("outfit") or context.get("outfit", [])
    makeup = payload_data.get("makeup") or context.get("makeup", [])
    poses = payload_data.get("poses") or context.get("poses", [])
    summary = str(payload_data.get("summary", "")).strip() or f"已结合{payload.style}风格、face_analysis 和 RAG 知识库生成建议。"
    result = SuggestResponse(outfit=outfit, makeup=makeup, poses=poses, summary=summary)
    logger.info("qwen_suggest_client response_parsed=%s", result.model_dump())
    return result  # 响应对象结束
