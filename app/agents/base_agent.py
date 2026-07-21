# -*- coding: utf-8 -*-
"""
Agent基类模块
定义了所有Agent的基础接口和通用功能
"""

from abc import ABC, abstractmethod
from typing import Optional
from app.graph.state import AgentState


class BaseAgent(ABC):
    """
    Agent基类
    所有具体的Agent都需要继承此类并实现execute方法
    """
    
    def __init__(self, name: str):
        """
        初始化Agent
        
        Args:
            name: Agent的名称
        """
        self.name = name  # Agent名称
        self.enabled = True  # 是否启用此Agent
    
    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """
        执行Agent的主要逻辑
        每个Agent需要实现此方法来处理状态
        
        Args:
            state: 当前的共享状态
            
        Returns:
            AgentState: 更新后的状态
        """
        pass
    
    def validate_input(self, state: AgentState) -> bool:
        """
        验证输入状态是否满足此Agent的执行条件
        子类可以重写此方法来添加自定义验证逻辑
        
        Args:
            state: 当前的共享状态
            
        Returns:
            bool: 验证是否通过
        """
        return True
    
    async def run(self, state: AgentState) -> AgentState:
        """
        运行Agent的完整流程
        包含验证、执行和错误处理
        
        Args:
            state: 当前的共享状态
            
        Returns:
            AgentState: 处理后的状态
        """
        # 检查Agent是否启用
        if not self.enabled:
            print(f"[{self.name}] Agent已禁用，跳过执行")
            return state
        
        # 验证输入
        if not self.validate_input(state):
            print(f"[{self.name}] 输入验证失败")
            raise ValueError(f"{self.name} 输入验证失败")
        
        # 执行Agent逻辑
        print(f"[{self.name}] 开始执行...")
        result_state = await self.execute(state)
        print(f"[{self.name}] 执行完成")
        
        return result_state
    
    def __str__(self) -> str:
        """返回Agent的字符串表示"""
        return f"{self.name}Agent"
