"""Build one bounded, immutable conversation snapshot for every chat backend."""

from dataclasses import dataclass
import json


MAX_CONTEXT_MESSAGES = 20
MAX_CONTEXT_CHARS = 12_000


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str


@dataclass(frozen=True)
class ChatRequest:
    system: str
    messages: tuple[ChatMessage, ...]


def build_chat_request(history, settings, mood_hint="", *,
                       max_messages=MAX_CONTEXT_MESSAGES, max_chars=MAX_CONTEXT_CHARS):
    """Keep the newest contiguous suffix; never silently cut the current user.

    Limits count conversation messages and Unicode characters, not model
    tokens. The system persona is separate. Display-only entries are excluded.
    """
    if max_messages < 1 or max_chars < 1:
        raise ValueError("上下文上限必须大于零")
    normalized = []
    for item in history:
        if not isinstance(item, dict) or item.get("include_in_context") is False:
            continue
        role = {"user": "user", "pet": "assistant", "assistant": "assistant"}.get(item.get("role"))
        content = item.get("content")
        if role and isinstance(content, str) and content.strip():
            normalized.append(ChatMessage(role, content))
    if not normalized or normalized[-1].role != "user":
        raise ValueError("请先输入当前要发送的消息")
    if len(normalized[-1].content) > max_chars:
        raise ValueError(f"消息过长，请缩短至 {max_chars} 个字符以内再发送。")
    selected = []
    size = 0
    for message in reversed(normalized):
        if len(selected) == max_messages or size + len(message.content) > max_chars:
            break
        selected.append(message)
        size += len(message.content)
    selected.reverse()
    while selected and selected[0].role == "assistant":
        selected.pop(0)

    def setting(key, default):
        value = settings.get(key)
        return value.strip() if isinstance(value, str) and value.strip() else default

    system = (
        f"你是一只可爱的桌面宠物边牧，名字叫{setting('pet_name', '边牧')}，"
        f"性格{setting('pet_personality', '活泼')}，"
        f"口头禅是\"{setting('pet_catchphrase', '汪~')}\"。"
        "根据当前对话回应用户，说话简短，通常回复 2-3 句，不要用 Markdown。"
        + mood_hint
    )
    return ChatRequest(system, tuple(selected))


def api_messages(request):
    return [{"role": "system", "content": request.system}] + [
        {"role": message.role, "content": message.content} for message in request.messages
    ]


def cli_prompt(request):
    """CLI text input is a JSON transcript; persona goes in --system-prompt."""
    return json.dumps(api_messages(request)[1:], ensure_ascii=False)
