import json  # 引入json用于序列化流式数据
from typing import Any  # 引入Any用于标注通用JSON对象

from app.graph import build_workflow  # 引入工作流构建函数
from app.schemas.llm import SuggestRequest, SuggestResponse  # 引入模型


def run_pipeline(payload: SuggestRequest) -> SuggestResponse:  # 运行完整调度流程
    workflow = build_workflow()  # 构建LangGraph工作流
    if workflow is None:  # 如果当前环境未安装LangGraph
        raise RuntimeError("LangGraph 未安装，无法运行建议生成流程")  # 直接暴露运行环境问题
    result = workflow.invoke({"request": payload})  # 运行工作流
    suggestion = result.get("suggestion")  # 读取生成结果
    if suggestion is None:  # 如果工作流未产出结果
        raise ValueError("工作流未返回 suggestion，请检查节点执行结果")  # 直接暴露工作流异常
    return SuggestResponse(**suggestion)  # 转换为响应模型


# def stream_pipeline(payload: SuggestRequest):  # 运行流式调度流程
#     workflow = build_workflow()  # 构建LangGraph工作流
#     if workflow is None:  # 如果当前环境未安装LangGraph
#         raise RuntimeError("LangGraph 未安装，无法运行流式建议生成流程")  # 直接暴露运行环境问题
#     for chunk in workflow.stream({"request": payload}):  # 以流式方式输出每个步骤结果
#         yield chunk  # 向外部逐步返回


def _to_json_safe(value: Any) -> Any:  # 将任意对象转换为可JSON序列化结构
    if hasattr(value, "model_dump") and callable(value.model_dump):  # 如果是Pydantic模型
        return _to_json_safe(value.model_dump())  # 递归转换模型
    if isinstance(value, dict):  # 如果是字典
        return {str(key): _to_json_safe(item) for key, item in value.items()}  # 递归转换字典内容
    if isinstance(value, list):  # 如果是列表
        return [_to_json_safe(item) for item in value]  # 递归转换列表内容
    if isinstance(value, tuple):  # 如果是元组
        return [_to_json_safe(item) for item in value]  # 转成列表便于JSON序列化
    if isinstance(value, set):  # 如果是集合
        return [_to_json_safe(item) for item in value]  # 转成列表便于JSON序列化
    if isinstance(value, (str, int, float, bool)) or value is None:  # 如果本身可直接序列化
        return value  # 直接返回
    return str(value)  # 其他对象统一转成字符串


def format_sse_event(event: str, data: dict) -> str:  # 格式化SSE事件
    safe_data = _to_json_safe(data)  # 先把数据转成可序列化结构
    return f"event: {event}\ndata: {json.dumps(safe_data, ensure_ascii=False)}\n\n"  # 返回SSE文本
