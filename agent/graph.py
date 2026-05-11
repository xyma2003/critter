from langgraph.graph import StateGraph, END
from .state import AgentState
from .nodes import (
    understand_intent,
    plan_task,
    execute_step,
    reflect_and_decide,
    respond_to_user
)


def should_continue_execution(state: AgentState) -> str:
    """判断执行后应该进入哪个节点"""
    steps_completed = state.get("steps_completed", [])
    plan = state.get("plan", [])
    last_result = state.get("tool_results", {}).get("last_execution", {})
    
    # 检查是否所有步骤都完成
    if len(steps_completed) >= len(plan):
        return "respond"
    
    # 检查上一步是否失败
    if last_result and not last_result.get("success", True):
        return "reflect"
    
    # 继续执行下一步
    return "execute"


def should_continue_after_reflection(state: AgentState) -> str:
    """判断反思后应该进入哪个节点"""
    reasoning = state.get("reasoning", "").lower()
    
    if "replan" in reasoning:
        return "plan"
    elif "abort" in reasoning:
        return "respond"
    else:
        return "execute"


def create_agent_graph():
    """创建并编译 LangGraph 工作流"""
    
    # 创建状态图
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("understand", understand_intent)
    workflow.add_node("plan", plan_task)
    workflow.add_node("execute", execute_step)
    workflow.add_node("reflect", reflect_and_decide)
    workflow.add_node("respond", respond_to_user)
    
    # 设置入口点
    workflow.set_entry_point("understand")
    
    # 定义边（状态转换）
    workflow.add_edge("understand", "plan")
    
    # 执行后的条件边
    workflow.add_conditional_edges(
        "execute",
        should_continue_execution,
        {
            "execute": "execute",      # 继续执行下一步
            "reflect": "reflect",      # 需要反思
            "respond": "respond"       # 完成任务
        }
    )
    
    # 计划后直接执行
    workflow.add_edge("plan", "execute")
    
    # 反思后的条件边
    workflow.add_conditional_edges(
        "reflect",
        should_continue_after_reflection,
        {
            "plan": "plan",           # 重新规划
            "execute": "execute",     # 继续执行
            "respond": "respond"      # 放弃任务
        }
    )
    
    # 回复后结束
    workflow.add_edge("respond", END)
    
    # 编译并返回
    return workflow.compile()
