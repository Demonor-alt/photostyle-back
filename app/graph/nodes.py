import json  # 引入json用于解析模型输出

from app.agents.evaluation_agent import evaluate_history  # 引入评价节点
from app.db.user_service import get_user_profile  # 引入用户资料查询
from app.rag.retriever import retrieve_context  # 引入检索节点
from app.services.styling_service import build_suggestion  # 引入Styling生成服务


def _log_step(step_name: str, payload: dict) -> None:  # 记录每一步的输入输出
    print(json.dumps({"step": step_name, "payload": payload}, ensure_ascii=False, indent=2), flush=True)  # 打印结构化调试信息


def retrieval_node(state: dict) -> dict:  # 检索节点
    request = state["request"]  # 获取请求对象
    _log_step("retrieval_node.input", {"request": request.model_dump()})  # 输出输入内容
    user_profile = get_user_profile(request.username)  # 查询当前用户资料
    face_analysis = user_profile.get("face_analysis") or request.face_analysis or {}  # 优先使用数据库里的 face_analysis
    retrieved_context = retrieve_context(request, parsed_input={
        "style": request.style,
        "location": request.location,
        "time": request.time,
        "weather": request.weather,
        "face_tags": request.face_tags,
        "shot_tags": request.shot_tags,
        "pose_tags": request.pose_tags,
        "extra_tags": request.extra_tags,
    }, image_analysis=face_analysis)  # 检索知识上下文
    result = {"retrieved_context": retrieved_context, "user_profile": user_profile, "face_analysis": face_analysis, **state}  # 组装输出结果
    _log_step("retrieval_node.output", {"retrieved_context": retrieved_context, "face_analysis": face_analysis})  # 输出处理结果
    return result  # 写回状态


def generation_node(state: dict) -> dict:  # 生成节点
    request = state["request"]  # 获取请求对象
    face_analysis = state.get("face_analysis", {})  # 获取人脸分析结果
    retrieved_context = state.get("retrieved_context", {})  # 获取检索结果
    _log_step("generation_node.input", {"request": request.model_dump(), "face_analysis": face_analysis, "retrieved_context": retrieved_context})  # 输出模型输入
    suggestion = build_suggestion(request, user_face_analysis=face_analysis)  # 调用Styling服务生成建议
    if not suggestion.outfit and not suggestion.makeup and not suggestion.poses:  # 如果大模型未返回有效建议
        raise ValueError("模型未返回有效建议，请检查上游服务和提示词配置")  # 直接报错暴露问题
    _log_step("generation_node.output", suggestion.model_dump())  # 输出模型输出
    return {"suggestion": suggestion.model_dump(), **state}  # 写回状态


def evaluation_node(state: dict) -> dict:  # 评价节点
    suggestion = state.get("suggestion", {})  # 获取建议内容
    _log_step("evaluation_node.input", {"suggestion": suggestion})  # 输出输入内容
    evaluation = evaluate_history({"liked": False, "shot_success": False, "suggestion": suggestion})  # 生成评价
    _log_step("evaluation_node.output", {"evaluation": evaluation})  # 输出处理结果
    return {"evaluation": evaluation, **state}  # 写回状态
