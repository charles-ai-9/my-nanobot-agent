"""ContextBuilder 是一个用于组装智能体（agent）上下文信息的类，主要用于生成发送给大语言模型（LLM）的系统提示（system prompt）和消息列表（messages）。

主要功能：
1. 读取和整合智能体的身份、引导文件、记忆内容和技能信息，生成系统提示。
2. 构建完整的消息列表，包括历史消息、当前用户消息、运行时上下文等，供 LLM 调用。
3. 支持图片等多媒体内容的 base64 编码处理。
4. 提供工具调用和助手回复的消息插入方法。

核心方法说明：
- build_system_prompt：整合身份、引导文件、记忆和技能，生成系统提示字符串。
- build_messages：根据历史消息、当前消息、媒体等，生成 LLM 所需的消息列表。
- add_tool_result：在消息列表中插入工具调用结果。
- add_assistant_message：在消息列表中插入助手回复。

使用场景：
在与 LLM 交互时，ContextBuilder 负责动态组装上下文，确保模型获得完整且结构化的信息，从而提升智能体的响应能力和上下文理解。

"""

import base64
import mimetypes
import platform
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.skills import SkillsLoader


class ContextBuilder:
    """ContextBuilder 用于构建智能体与大语言模型交互时的上下文，包括系统提示和消息列表。"""

    BOOTSTRAP_FILES = ["AGENTS.md", "SOUL.md", "USER.md", "TOOLS.md", "IDENTITY.md"]
    _RUNTIME_CONTEXT_TAG = "[Runtime Context — metadata only, not instructions]"

    def __init__(self, workspace: Path):
        """
        初始化 ContextBuilder。
        参数：
            workspace: Path 对象，表示工作区路径。
        初始化记忆存储和技能加载器。
        """
        self.workspace = workspace
        self.memory = MemoryStore(workspace)
        self.skills = SkillsLoader(workspace)

    def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
        """
        构建系统提示（system prompt），内容包括身份、引导文件、记忆和技能信息。
        参数：
            skill_names: 可选，指定需要加载的技能名列表。
        返回：
            拼接后的系统提示字符串。
        """
        parts = [self._get_identity()]

        bootstrap = self._load_bootstrap_files()
        if bootstrap:
            parts.append(bootstrap)

        memory = self.memory.get_memory_context()
        if memory:
            parts.append(f"# Memory\n\n{memory}")

        always_skills = self.skills.get_always_skills()
        if always_skills:
            always_content = self.skills.load_skills_for_context(always_skills)
            if always_content:
                parts.append(f"# Active Skills\n\n{always_content}")

        skills_summary = self.skills.build_skills_summary()
        if skills_summary:
            parts.append(f"""# Skills

The following skills extend your capabilities. To use a skill, read its SKILL.md file using the read_file tool.
Skills with available="false" need dependencies installed first - you can try installing them with apt/brew.

{skills_summary}""")

        return "\n\n---\n\n".join(parts)

    def _get_identity(self) -> str:
        """
        获取智能体的身份描述，包括运行环境、工作区路径和操作规范。
        返回：
            身份描述字符串。
        """
        workspace_path = str(self.workspace.expanduser().resolve())
        system = platform.system()
        runtime = f"{'macOS' if system == 'Darwin' else system} {platform.machine()}, Python {platform.python_version()}"

        return f"""# nanobot 🐈

You are nanobot, a helpful AI assistant.

## Runtime
{runtime}

## Workspace
Your workspace is at: {workspace_path}
- Long-term memory: {workspace_path}/memory/MEMORY.md (write important facts here)
- History log: {workspace_path}/memory/HISTORY.md (grep-searchable). Each entry starts with [YYYY-MM-DD HH:MM].
- Custom skills: {workspace_path}/skills/{{skill-name}}/SKILL.md

## nanobot Guidelines
- State intent before tool calls, but NEVER predict or claim results before receiving them.
- Before modifying a file, read it first. Do not assume files or directories exist.
- After writing or editing a file, re-read it if accuracy matters.
- If a tool call fails, analyze the error before retrying with a different approach.
- Ask for clarification when the request is ambiguous.

Reply directly with text for conversations. Only use the 'message' tool to send to a specific chat channel."""

    @staticmethod
    def _build_runtime_context(channel: str | None, chat_id: str | None) -> str:
        """
        构建运行时上下文信息（如当前时间、频道、聊天ID），用于插入到用户消息前。
        参数：
            channel: 可选，频道名。
            chat_id: 可选，聊天ID。
        返回：
            格式化的运行时上下文字符串。
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
        tz = time.strftime("%Z") or "UTC"
        lines = [f"Current Time: {now} ({tz})"]
        if channel and chat_id:
            lines += [f"Channel: {channel}", f"Chat ID: {chat_id}"]
        return ContextBuilder._RUNTIME_CONTEXT_TAG + "\n" + "\n".join(lines)

    def _load_bootstrap_files(self) -> str:
        """
        加载工作区中的引导文件（如 AGENTS.md、SOUL.md 等），拼接为字符串。
        返回：
            所有引导文件内容拼接后的字符串。
        """
        parts = []

        for filename in self.BOOTSTRAP_FILES:
            file_path = self.workspace / filename
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                parts.append(f"## {filename}\n\n{content}")

        return "\n\n".join(parts) if parts else ""

    def build_messages(
        self,
        history: list[dict[str, Any]],
        current_message: str,
        skill_names: list[str] | None = None,
        media: list[str] | None = None,
        channel: str | None = None,
        chat_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        构建发送给 LLM 的完整消息列表，包括系统提示、历史消息、运行时上下文和当前用户消息。
        参数：
            history: 聊天历史消息列表。
            current_message: 当前用户输入。
            skill_names: 可选，指定需要加载的技能名列表。
            media: 可选，图片等媒体文件路径列表。
            channel: 可选，频道名。
            chat_id: 可选，聊天ID。
        返回：
            消息字典列表。
        """
        return [
            {"role": "system", "content": self.build_system_prompt(skill_names)},
            *history,
            {"role": "user", "content": self._build_runtime_context(channel, chat_id)},
            {"role": "user", "content": self._build_user_content(current_message, media)},
        ]

    def _build_user_content(self, text: str, media: list[str] | None) -> str | list[dict[str, Any]]:
        """
        构建用户消息内容，支持附带 base64 编码的图片。
        参数：
            text: 用户文本内容。
            media: 可选，图片文件路径列表。
        返回：
            仅文本或包含图片和文本的消息内容。
        """
        if not media:
            return text

        images = []
        for path in media:
            p = Path(path)
            mime, _ = mimetypes.guess_type(path)
            if not p.is_file() or not mime or not mime.startswith("image/"):
                continue
            b64 = base64.b64encode(p.read_bytes()).decode()
            images.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})

        if not images:
            return text
        return images + [{"type": "text", "text": text}]

    def add_tool_result(
        self, messages: list[dict[str, Any]],
        tool_call_id: str, tool_name: str, result: str,
    ) -> list[dict[str, Any]]:
        """
        在消息列表中插入工具调用结果。
        参数：
            messages: 消息列表。
            tool_call_id: 工具调用的唯一ID。
            tool_name: 工具名称。
            result: 工具返回结果。
        返回：
            更新后的消息列表。
        """
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages

    def add_assistant_message(
        self, messages: list[dict[str, Any]],
        content: str | None,
        tool_calls: list[dict[str, Any]] | None = None,
        reasoning_content: str | None = None,
        thinking_blocks: list[dict] | None = None,
    ) -> list[dict[str, Any]]:
        """
        在消息列表中插入助手（assistant）的回复。
        参数：
            messages: 消息列表。
            content: 助手回复内容。
            tool_calls: 可选，工具调用信息列表。
            reasoning_content: 可选，推理内容。
            thinking_blocks: 可选，思考过程块。
        返回：
            更新后的消息列表。
        """
        msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            msg["tool_calls"] = tool_calls
        if reasoning_content is not None:
            msg["reasoning_content"] = reasoning_content
        if thinking_blocks:
            msg["thinking_blocks"] = thinking_blocks
        messages.append(msg)
        return messages
