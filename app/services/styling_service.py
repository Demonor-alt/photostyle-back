from app.schemas.history import SuggestRequest, SuggestResponse  # 引入请求响应模型
from app.services.llm.qwen_suggest_client import generate_suggestion  # 引入Qwen建议生成客户端


def build_suggestion(payload: SuggestRequest, user_face_analysis: dict | None = None) -> SuggestResponse:  # 构建最终建议结果
    return generate_suggestion(payload, user_face_analysis=user_face_analysis)  # 交给独立客户端生成建议
