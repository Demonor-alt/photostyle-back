try:  # 尝试导入LangGraph
    from langgraph.graph import StateGraph, END  # 引入LangGraph状态图
    from langgraph.checkpoint.memory import MemorySaver  # 引入内存检查点
except Exception:  # 如果当前环境未安装依赖
    StateGraph = None  # 降级为空
    END = None  # 降级为空
    MemorySaver = None  # 降级为空

from app.graph.state import PhotoStyleState  # 引入状态类型
from app.graph.nodes import retrieval_node, generation_node, evaluation_node  # 引入节点函数


def build_workflow():  # 构建LangGraph工作流
    if StateGraph is None:  # 如果未安装LangGraph
        return None  # 返回空，保留骨架
    graph = StateGraph(PhotoStyleState)  # 创建状态图
    graph.add_node("retrieval", retrieval_node)  # 添加检索节点
    graph.add_node("generation", generation_node)  # 添加生成节点
    graph.add_node("evaluation_node", evaluation_node)  # 添加评价节点
    graph.set_entry_point("retrieval")  # 设置入口节点
    graph.add_edge("retrieval", "generation")  # 检索后进入生成
    graph.add_edge("generation", "evaluation_node")  # 生成后进入评价
    graph.add_edge("evaluation_node", END)  # 评价后结束
    return graph.compile()  # 编译并返回可执行工作流
