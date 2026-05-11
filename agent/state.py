from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
import operator


class AgentState(TypedDict):
    """LangGraph Agent 的状态定义"""

    # 对话历史
    messages: Annotated[Sequence[BaseMessage], operator.add]

    # 当前任务描述
    current_task: str

    # 任务执行计划（步骤列表）
    plan: list[str]

    # 已完成的步骤
    steps_completed: list[str]

    # 工具调用结果
    tool_results: dict

    # Agent 的推理过程
    reasoning: str

    # 是否需要人工确认
    needs_human_approval: bool

    # 当前执行状态
    status: str  # "planning", "executing", "reflecting", "done", "error"
