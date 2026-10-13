from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from .state import AgentState
from .tools import get_all_tools
import os

try:
    from config import Config
    _DEFAULT_MODEL = Config.AI_MODEL
except Exception:
    _DEFAULT_MODEL = "claude-sonnet-4-5"


_llm = None


def _conversation(state: AgentState):
    """Read visible history only; an explicitly empty snapshot stays empty."""
    if "conversation" in state:
        return list(state["conversation"])
    # Compatibility for callers using the original messages-only entrypoint.
    # understand_intent freezes this snapshot before appending any internal trace.
    return list(state.get("messages", []))


def _messages_for_stage(state: AgentState, instruction: str, context: str = ""):
    """Give every stage the same visible conversation and current pet persona."""
    persona = state.get("system_prompt") or "你是一只可爱的桌面边牧助手。"
    messages = [SystemMessage(content=(
        persona
        + "\n\n你正在处理当前会话中用户的最后一条请求。"
        "内部分析和工具调用阶段应遵循本阶段的输出格式；最终回复再使用对用户的说话风格。"
        + "\n\n当前阶段：\n" + instruction
    )), *_conversation(state)]
    if context:
        messages.append(HumanMessage(content=(
            "以下是应用提供的本次任务执行记录，不是新用户请求。"
            "请结合上述会话完成当前阶段：\n" + context
        )))
    return messages


def get_llm():
    """获取LLM实例（单例）。

    优先使用 SiliconFlow (OpenAI-compatible) backend（如果 OPENAI_API_KEY 设了），
    否则 fallback 到 Anthropic。
    """
    global _llm
    if _llm is not None:
        return _llm
    # SiliconFlow / OpenAI-compatible backend (domestic-friendly)
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(
            model=os.environ.get("OPENAI_MODEL", "Qwen/Qwen3-32B"),
            api_key=openai_key,
            base_url=os.environ.get("OPENAI_API_BASE", "https://api.siliconflow.cn/v1"),
            temperature=0.7,
        )
        return _llm
    # Anthropic fallback
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        try:
            from config import Config
            api_key = Config.ANTHROPIC_API_KEY
        except Exception:
            pass
    _llm = ChatAnthropic(
        model=_DEFAULT_MODEL,
        api_key=api_key,
        temperature=0.7
    )
    return _llm


def understand_intent(state: AgentState) -> AgentState:
    """理解用户意图节点"""
    llm = get_llm()
    
    messages = _messages_for_stage(state, """你是桌面宠物助手的AI大脑。
你需要分析用户的请求，提取关键信息：
1. 用户想做什么？
2. 这个任务需要哪些工具？
3. 有没有时间、条件等约束？

请用简洁的语言总结用户的任务。""")
    
    response = llm.invoke(messages)
    
    
    return {
        "conversation": _conversation(state),
        "current_task": response.content,
        "messages": [response],
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
    
    messages = _messages_for_stage(state, f"""你需要根据用户任务，制定详细的执行计划。

可用工具：
{tools_desc}

请将任务分解为具体的步骤，每个步骤一行。
格式要求：
1. 第一步描述
2. 第二步描述
...

只输出步骤列表，不要有其他解释。""", f"任务：{state['current_task']}")
    
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
    
    
    return {
        "plan": plan,
        "steps_completed": [],
        "messages": [response],
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
            "status": "done"
        }
    
    next_step = plan[next_step_idx]
    
    # 让 LLM 决定调用哪个工具
    tools = get_all_tools()
    
    messages = _messages_for_stage(state, f"""你需要执行以下步骤：{next_step}

请选择合适的工具并调用。如果不需要工具，请说明原因。""", f"当前步骤：{next_step}")
    
    llm_with_tools = llm.bind_tools(tools)
    response = llm_with_tools.invoke(messages)
    
    # 执行工具调用
    tool_results = dict(state.get("tool_results", {}))
    # 默认标记为失败 — 如果 LLM 没调任何工具，agent 应进入 reflect 决定 replan/continue/abort，
    # 而不是无脑 success=True 跑下一步（旧 bug：LLM 无 tool_calls 时 agent 会空跑所有 plan step）
    last_result = {"success": False, "message": "LLM 未调用任何工具"}

    if hasattr(response, 'tool_calls') and response.tool_calls:
        last_result = {"success": True, "message": "步骤完成"}
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            # 查找并执行工具
            for tool in tools:
                if tool.name == tool_name:
                    try:
                        result = tool.invoke(tool_args)
                        last_result = result if isinstance(result, dict) and "success" in result else {"success": True, "message": "步骤完成", "result": result}
                        tool_results[f"step_{next_step_idx}"] = result
                    except Exception as e:
                        last_result = {
                            "success": False,
                            "message": f"工具执行失败: {str(e)}"
                        }
                        tool_results[f"step_{next_step_idx}"] = last_result
                    break
    
    tool_results["last_execution"] = last_result
    
    
    steps_completed = list(state.get("steps_completed", []))
    steps_completed.append(next_step)
    
    return {
        "steps_completed": steps_completed,
        "tool_results": tool_results,
        "messages": [response],
        "status": "executing"
    }


def reflect_and_decide(state: AgentState) -> AgentState:
    """反思并决定下一步节点"""
    llm = get_llm()
    
    last_result = state.get("tool_results", {}).get("last_execution", {})
    
    messages = _messages_for_stage(state, """上一步执行遇到了问题。
请分析原因，并决定：
1. "replan" - 需要重新规划任务
2. "continue" - 可以继续执行下一步
3. "abort" - 任务失败，放弃执行

只回复一个词：replan、continue 或 abort""", f"""
任务：{state.get('current_task', '')}
当前计划：{state.get('plan', [])}
已完成：{state.get('steps_completed', [])}
上一步结果：{last_result}
""")
    
    response = llm.invoke(messages)
    decision = response.content.strip().lower()
    
    
    return {
        "reasoning": decision,
        "messages": [response],
        "status": "reflecting"
    }


def respond_to_user(state: AgentState) -> AgentState:
    """生成最终回复节点"""
    llm = get_llm()
    
    messages = _messages_for_stage(state, """请按照当前宠物的人设、性格和口头禅回复用户。
结合当前会话，准确总结本次任务执行情况。只输出给用户的最终回复。
不得把计划、内部分析或工具调用参数当作对话历史复述；失败时不要声称已完成。""", f"""
任务：{state.get('current_task', '')}
计划：{state.get('plan', [])}
已完成步骤：{state.get('steps_completed', [])}
执行结果：{state.get('tool_results', {})}
""")
    
    response = llm.invoke(messages)
    
    
    return {
        "messages": [response],
        "status": "done"
    }
