# -*- coding: utf-8 -*-
"""
LLM服务模块
包含与大语言模型相关的客户端实现
"""

from .qwen_face_client import analyze_image
from .qwen_suggest_client import generate_suggestion

__all__ = [
    "analyze_image",
    "generate_suggestion",
]
