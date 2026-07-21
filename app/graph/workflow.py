# -*- coding: utf-8 -*-
"""
Agent工作流模块
定义了Agent的执行流程和编排逻辑
"""

from typing import List
from app.graph.state import AgentState
from app.agents.base_agent import BaseAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.search_agent import SearchAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.fusion_agent import FusionAgent
from app.agents.generator_agent import GeneratorAgent
from app.agents.critic_agent import CriticAgent


class AgentWorkflow:
    """
    Agent工作流类
    管理多个Agent的顺序执行流程
    """
    
    def __init__(self):
        """初始化工作流，创建所有Agent实例"""
        # 按照流程顺序初始化所有Agent
        self.agents: List[BaseAgent] = [
            PlannerAgent(),      # 1. 计划Agent
            SearchAgent(),       # 2. 搜索Agent
            MemoryAgent(),       # 3. 记忆Agent
            FusionAgent(),       # 4. 融合Agent
            GeneratorAgent(),    # 5. 生成Agent
            CriticAgent(),       # 6. 评论Agent
        ]
    
    async def execute(self, initial_state: AgentState) -> AgentState:
        """
        执行完整的Agent工作流
        按顺序执行所有Agent，每个Agent逐步扩展state
        
        Args:
            initial_state: 初始状态（包含用户输入等）
            
        Returns:
            AgentState: 最终处理后的状态
        """
        # 从初始状态开始
        current_state = initial_state
        
        # 依次执行每个Agent
        for agent in self.agents:
            try:
                # 执行当前Agent，获取更新后的状态
                current_state = await agent.run(current_state)
            except Exception as e:
                # 记录错误信息到metadata
                error_info = {
                    "agent": agent.name,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                current_state.metadata.setdefault("errors", []).append(error_info)
                print(f"[Workflow] {agent.name} Agent执行失败: {e}")
                # 根据错误严重程度决定是否继续
                # 这里可以添加更复杂的错误处理逻辑
                raise
        
        return current_state
    
    def get_agent_by_name(self, name: str) -> BaseAgent:
        """
        根据名称获取Agent实例
        
        Args:
            name: Agent名称
            
        Returns:
            BaseAgent: 对应的Agent实例，如果不存在返回None
        """
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None
    
    def enable_agent(self, name: str):
        """
        启用指定的Agent
        
        Args:
            name: Agent名称
        """
        agent = self.get_agent_by_name(name)
        if agent:
            agent.enabled = True
            print(f"[Workflow] {name} Agent已启用")
    
    def disable_agent(self, name: str):
        """
        禁用指定的Agent
        
        Args:
            name: Agent名称
        """
        agent = self.get_agent_by_name(name)
        if agent:
            agent.enabled = False
            print(f"[Workflow] {name} Agent已禁用")
