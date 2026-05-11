from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from .state import AgentState
from .tools import get_all_tools
import json
import os


_llm = None


def get_llm():
    """获取LLM实例（单例）"""
    global _llm
    if _llm is not None:
        return _llm
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            from config import Config
            api_key = Config.ANTHROPIC_API_KEY
        except Exception:
            pass
    _llm = ChatAnthropic(
        model="claude-3-5-sonnet-20241022",
        api_key=api_key,
        temperature=0.7
    )
    return _llm


def understand_intent(state: AgentState) -> AgentState:
    """理解用户意图节点"""
    llm = get_llm()
    
    user_message = state["messages"][-1].content if state["messages"] else ""
    
    messages = [
        SystemMessage(content="""你是一个桌面边牧助手的AI大脑。
你需要分析用户的请求，提取关键信息：
1. 用户想做什么？
2. 这个任务需要哪些工具？
3. 有没有时间、条件等约束？

请用简洁的语言总结用户的任务。"""),
        HumanMessage(content=f"用户请求：{user_message}")
    ]
    
    response = llm.invoke(messages)
    
    new_messages = list(state.get("messages", []))
    new_messages.append(response)
    
    return {
        **state,
        "current_task": response.content,
        "messages": new_messages,
        "status": "planning"
    }


def plan_task(state: AgentState) -> AgentState:
    """规划任务步骤节点"""
    llm = get_llm()
    
    tools = get_all_tools()
    tools_desc = "\n".join([
        f"- {tool.name}: {tool.description}"
        for tool in tools
    ])
    
    messages = [
        SystemMessage(content=f"""你需要根据用户任务，制定详细的执行计划。

可用工具：
{tools_desc}

请将任务分解为具体的步骤，每个步骤一行。
格式要求：
1. 第一步描述
2. 第二步描述
...

只输出步骤列表，不要有其他解释。"""),
        HumanMessage(content=f"任务：{state['current_task']}")
    ]
    
    response = llm.invoke(messages)
    
    # 解析计划
    plan_text = response.content.strip()
    plan = []
    for line in plan_text.split("\n"):
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            # 移除序号
            step = line.split(".", 1)[-1].strip() if "." in line else line.lstrip("- ")
            plan.append(step)
    
    new_messages = list(state.get("messages", []))
    new_messages.append(response)
    
    return {
        **state,
        "plan": plan,
        "steps_completed": [],
        "messages": new_messages,
        "status": "executing"
    }


def execute_step(state: AgentState) -> AgentState:
    """执行下一步节点"""
    llm = get_llm()
    
    # 获取下一步
    next_step_idx = len(state.get("steps_completed", []))
    plan = state.get("plan", [])
    
    if next_step_idx >= len(plan):
        # 所有步骤已完成
        return {
            **state,
            "status": "done"
        }
    
    next_step = plan[next_step_idx]
    
    # 让 LLM 决定调用哪个工具
    tools = get_all_tools()
    
    messages = [
        SystemMessage(content=f"""你需要执行以下步骤：{next_step}

请选择合适的工具并调用。如果不需要工具，请说明原因。"""),
        HumanMessage(content=f"当前步骤：{next_step}")
    ]
    
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(messages)
    
    # 执行工具调用
    tool_results = state.get("tool_results", {})
    last_result = {"success": True, "message": "步骤完成"}
    
    if hasattr(response, 'tool_calls') and response.tool_calls:
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            # 查找并执行工具
            for tool in tools:
                if tool.name == tool_name:
                    try:
                        result = tool.invoke(tool_args)
                        last_result = result
                        tool_results[f"step_{next_step_idx}"] = result
                    except Exception as e:
                        last_result = {
                            "success": False,
                            "message": f"工具执行失败: {str(e)}"
                        }
                        tool_results[f"step_{next_step_idx}"] = last_result
                    break
    
    tool_results["last_execution"] = last_result
    
    new_messages = list(state.get("messages", []))
    new_messages.append(response)
    
    steps_completed = list(state.get("steps_completed", []))
    steps_completed.append(next_step)
    
    return {
        **state,
        "steps_completed": steps_completed,
        "tool_results": tool_results,
        "messages": new_messages,
        "status": "executing"
    }


def reflect_and_decide(state: AgentState) -> AgentState:
    """反思并决定下一步节点"""
    llm = get_llm()
    
    last_result = state.get("tool_results", {}).get("last_execution", {})
    
    messages = [
        SystemMessage(content="""上一步执行遇到了问题。
请分析原因，并决定：
1. "replan" - 需要重新规划任务
2. "continue" - 可以继续执行下一步
3. "abort" - 任务失败，放弃执行

只回复一个词：replan、continue 或 abort"""),
        HumanMessage(content=f"""
任务：{state.get('current_task', '')}
当前计划：{state.get('plan', [])}
已完成：{state.get('steps_completed', [])}
上一步结果：{last_result}
""")
    ]
    
    response = llm.invoke(messages)
    decision = response.content.strip().lower()
    
    new_messages = list(state.get("messages", []))
    new_messages.append(response)
    
    return {
        **state,
        "reasoning": decision,
        "messages": new_messages,
        "status": "reflecting"
    }


def respond_to_user(state: AgentState) -> AgentState:
    """生成最终回复节点"""
    llm = get_llm()
    
    messages = [
        SystemMessage(content="""你是一只可爱的边牧助手。
请用友好、活泼的语气总结任务执行情况，回复用户。
如果任务成功，要表现得开心；如果失败，要表示歉意。"""),
        HumanMessage(content=f"""
任务：{state.get('current_task', '')}
计划：{state.get('plan', [])}
已完成步骤：{state.get('steps_completed', [])}
执行结果：{state.get('tool_results', {})}
""")
    ]
    
    response = llm.invoke(messages)
    
    new_messages = list(state.get("messages", []))
    new_messages.append(response)
    
    return {
        **state,
        "messages": new_messages,
        "status": "done"
    }
