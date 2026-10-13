"""Run the real LangGraph workflow with a scripted model and inert tools."""

import copy
import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agent import create_agent_graph
from agent import nodes


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.bound_tools = []

    def invoke(self, messages):
        self.calls.append(copy.deepcopy(messages))
        if not self.responses:
            raise AssertionError("Unexpected model call")
        return self.responses.pop(0)

    def bind_tools(self, tools):
        self.bound_tools.append(list(tools))
        return self


class AgentContextTests(unittest.TestCase):
    PERSONA = "你叫小栗，性格沉稳，口头禅是慢慢来，简短回复。"

    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex",
                       "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("Network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        self.conversation = [
            HumanMessage(content="我住在杭州，今天想早点休息。"),
            AIMessage(content="好，我记住了，慢慢来。"),
            HumanMessage(content="帮我查一下这里的天气，再定一个十分钟的计时器。"),
        ]
        self.tool = Mock()
        self.tool.name = "test_tool"
        self.tool.description = "An inert test tool that never accesses the network."
        self.tool.invoke.return_value = {"success": True, "message": "fixture only"}

    def initial_state(self, conversation=None):
        return {
            "messages": [],
            "conversation": copy.deepcopy(self.conversation if conversation is None else conversation),
            "system_prompt": self.PERSONA,
            "current_task": "", "plan": [], "steps_completed": [],
            "tool_results": {}, "reasoning": "",
            "needs_human_approval": False, "status": "planning",
        }

    @staticmethod
    def tool_response(identifier):
        return AIMessage(content="internal tool choice", tool_calls=[{
            "name": "test_tool", "args": {"fixture": identifier}, "id": identifier,
        }])

    def run_graph(self, responses, initial=None, graph=None):
        model = ScriptedModel(responses)
        initial = self.initial_state() if initial is None else initial
        with patch.object(nodes, "get_llm", return_value=model), \
                patch.object(nodes, "get_all_tools", return_value=[self.tool]):
            result = (graph or create_agent_graph()).invoke(initial)
        self.assertEqual(model.responses, [], "All scripted stages must execute")
        return result, model

    def assert_visible_context(self, model, conversation=None):
        expected = self.conversation if conversation is None else conversation
        for messages in model.calls:
            self.assertIsInstance(messages[0], SystemMessage)
            self.assertIn(self.PERSONA, messages[0].content)
            self.assertEqual(messages[1:1 + len(expected)], expected)
            # Internal model outputs and tool calls must not become prior replies.
            visible_assistants = [message for message in messages if isinstance(message, AIMessage)]
            self.assertEqual(visible_assistants, [message for message in expected
                                                 if isinstance(message, AIMessage)])
            self.assertFalse(any(message.tool_calls for message in visible_assistants))
            for message in expected:
                self.assertEqual(sum(item == message for item in messages), 1)

    def test_each_stage_receives_persona_and_visible_context_without_trace_pollution(self):
        responses = [
            AIMessage(content="internal intent summary"),
            AIMessage(content="1. 查询天气\n2. 设置计时器"),
            self.tool_response("weather"), self.tool_response("timer"),
            AIMessage(content="小栗帮你查好并设置了计时器，慢慢来。"),
        ]
        initial = self.initial_state()
        original = copy.deepcopy(initial)
        result, model = self.run_graph(responses, initial)
        self.assertEqual(initial, original, "Nodes must not mutate the request snapshot")
        self.assertEqual(result["messages"], responses)
        self.assertEqual(result["conversation"], self.conversation)
        self.assertEqual(result["system_prompt"], self.PERSONA)
        self.assertEqual(result["status"], "done")
        self.assertEqual(len(model.calls), 5)
        self.assertEqual(self.tool.invoke.call_count, 2)
        self.assert_visible_context(model)
        self.assertIn("只输出给用户的最终回复", model.calls[-1][0].content)

    def test_empty_plan_does_not_append_all_prior_messages_again(self):
        responses = [AIMessage(content="intent"), AIMessage(content="无需工具"),
                     AIMessage(content="这里是最后的回复")]
        result, model = self.run_graph(responses)
        self.assertEqual(result["messages"], responses)
        self.assertEqual(result["plan"], [])
        self.assertEqual(len(model.calls), 3)
        self.tool.invoke.assert_not_called()
        self.assert_visible_context(model)

    def test_failed_tool_reflection_keeps_same_context_and_one_trace_per_stage(self):
        self.tool.invoke.side_effect = RuntimeError("fixture failure")
        responses = [
            AIMessage(content="intent"), AIMessage(content="1. 尝试工具"),
            self.tool_response("failure"), AIMessage(content="abort"),
            AIMessage(content="暂时没能完成，慢慢来。"),
        ]
        result, model = self.run_graph(responses)
        self.assertEqual(result["messages"], responses)
        self.assertEqual(result["reasoning"], "abort")
        self.assertFalse(result["tool_results"]["last_execution"]["success"])
        self.assertEqual(len(model.calls), 5)
        self.assertIn("fixture failure", model.calls[3][-1].content)
        self.assert_visible_context(model)

    def test_replanning_does_not_reuse_internal_messages_as_conversation(self):
        responses = [
            AIMessage(content="intent"), AIMessage(content="1. 先尝试"),
            AIMessage(content="internal response without any tool call"),
            AIMessage(content="replan"), AIMessage(content="1. 再尝试"),
            self.tool_response("retry"), AIMessage(content="最终回复"),
        ]
        result, model = self.run_graph(responses)
        self.assertEqual(result["messages"], responses)
        self.assertEqual(len(model.calls), 7)
        self.assert_visible_context(model)

    def test_fresh_invocations_of_same_graph_do_not_share_conversation_or_trace(self):
        graph = create_agent_graph()
        first_responses = [AIMessage(content="first private intent"),
                           AIMessage(content="无需工具"), AIMessage(content="first reply")]
        self.run_graph(first_responses, graph=graph)
        fresh = [HumanMessage(content="这是完全不同的新对话")]
        responses = [AIMessage(content="fresh intent"), AIMessage(content="无需工具"),
                     AIMessage(content="fresh reply")]
        result, model = self.run_graph(responses, self.initial_state(fresh), graph)
        self.assertEqual(result["messages"], responses)
        self.assertEqual(result["conversation"], fresh)
        self.assert_visible_context(model, fresh)
        for messages in model.calls:
            text = "\n".join(message.content for message in messages)
            self.assertNotIn("杭州", text)
            self.assertNotIn("first private", text)

    def test_explicitly_empty_conversation_never_falls_back_to_internal_trace(self):
        initial = self.initial_state([])
        old_trace = AIMessage(content="private internal trace")
        initial["messages"] = [old_trace]
        responses = [AIMessage(content="intent"), AIMessage(content="无需工具"),
                     AIMessage(content="reply")]
        result, model = self.run_graph(responses, initial)
        self.assertEqual(result["messages"], [old_trace, *responses])
        self.assertEqual(result["conversation"], [])
        self.assert_visible_context(model, [])
        for messages in model.calls:
            self.assertNotIn(old_trace, messages)

    def test_legacy_messages_only_input_is_frozen_before_internal_trace_is_added(self):
        initial = self.initial_state()
        del initial["conversation"]
        initial["messages"] = copy.deepcopy(self.conversation)
        responses = [AIMessage(content="intent"), AIMessage(content="无需工具"),
                     AIMessage(content="reply")]
        result, model = self.run_graph(responses, initial)
        self.assertEqual(result["messages"], [*self.conversation, *responses])
        self.assertEqual(result["conversation"], self.conversation)
        self.assert_visible_context(model)


if __name__ == "__main__":
    unittest.main()
