# -*- coding: utf-8 -*-
"""
Agent状态定义模块
定义了多个Agent之间共享的状态结构
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class AgentState:
    """
    Agent共享状态类
    所有Agent按照流程顺序逐步扩展此状态
    """
    
    # 用户输入的原始数据（标签等）
    input: Dict[str, Any] = field(default_factory=dict)
    
    # 人脸特征数据（从图像中提取）
    face_features: Dict[str, Any] = field(default_factory=dict)
    
    # 预处理后的用户上下文（如历史记录数量等）
    context: Dict[str, Any] = field(default_factory=dict)
    
    # Planner Agent的输出结果（计划和策略）
    plan: Dict[str, Any] = field(default_factory=dict)
    
    # Search Agent的输出结果（搜索到的相关信息）
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Memory Agent的输出结果（记忆相关信息）
    memory: Dict[str, Any] = field(default_factory=dict)
    
    # Fusion Agent的输出结果（融合后的候选项）
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    
    # Generator Agent的最终输出结果
    final_output: Dict[str, Any] = field(default_factory=dict)
    
    # 可选：用于存储中间处理的元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将状态转换为字典格式
        
        Returns:
            Dict[str, Any]: 状态的字典表示
        """
        return {
            "input": self.input,
            "face_features": self.face_features,
            "context": self.context,
            "plan": self.plan,
            "search_results": self.search_results,
            "memory": self.memory,
            "candidates": self.candidates,
            "final_output": self.final_output,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """
        从字典创建状态对象
        
        Args:
            data: 包含状态数据的字典
            
        Returns:
            AgentState: 新的状态对象
        """
        return cls(
            input=data.get("input", {}),
            face_features=data.get("face_features", {}),
            context=data.get("context", {}),
            plan=data.get("plan", {}),
            search_results=data.get("search_results", []),
            memory=data.get("memory", {}),
            candidates=data.get("candidates", []),
            final_output=data.get("final_output", {}),
            metadata=data.get("metadata", {})
        )
