# -*- coding: utf-8 -*-
"""
LangGraph工作流模块
当前工作流仅保留Generator节点，直接调用Qwen建议生成客户端。
"""

from __future__ import annotations

import logging
from typing import TypedDict, NotRequired, Any

from app.schemas.history import SuggestRequest
from app.services.llm.qwen_suggest_client import generate_suggestion

logger = logging.getLogger(__name__)


try:
    from langgraph.graph import END, StateGraph  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - 在未安装LangGraph时提供降级能力
    END = None
    StateGraph = None


class WorkflowState(TypedDict, total=False):
    request: SuggestRequest
    suggestion: NotRequired[dict[str, Any]]


def generator_node(state: WorkflowState) -> WorkflowState:
    """LangGraph节点：直接调用Qwen建议生成器。"""
    request = state.get("request")
    if request is None:
        raise ValueError("workflow state missing request")

    logger.info("workflow.generator.request=%s", request.model_dump_json())
    suggestion = generate_suggestion(request)
    logger.info("workflow.generator.response=%s", suggestion.model_dump_json())
    return {"suggestion": suggestion.model_dump()}


class _FallbackWorkflow:
    """当环境未安装LangGraph时的轻量降级对象。"""

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        return generator_node(state)  # type: ignore[arg-type]


def build_workflow():
    """构建建议生成工作流。"""
    if StateGraph is None:
        logger.warning("LangGraph 未安装，使用降级工作流执行 Generator 节点")
        return _FallbackWorkflow()

    graph = StateGraph(WorkflowState)
    graph.add_node("generator", generator_node)
    graph.set_entry_point("generator")
    graph.add_edge("generator", END)
    return graph.compile()
