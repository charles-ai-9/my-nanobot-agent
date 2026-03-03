"""Memory system for persistent agent memory."""

## 这是一个非常实用的 Agent 记忆脚手架。它让 AI 具备了“自我整理”的能力：把冗长的对话变薄，把重要的信息留长。


from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from nanobot.utils.helpers import ensure_dir

if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.session.manager import Session

# 定义 LLM 工具调用的 schema，要求模型用 save_memory 工具保存记忆整合结果
# 在 Python 代码中直接用原生数据结构（列表 + 字典）比 JSON 字符串更高效、更易维护
_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            # 定义工具名称和参数 schema，LLM 需要按照这个 schema 返回结果
            "name": "save_memory",
            "description": "Save the memory consolidation result to persistent storage.",
            "parameters": {
                "type": "object",
                "properties": {
                    # history_entry 用于写入 HISTORY.md，便于全文检索
                    "history_entry": {
                        "type": "string",
                        "description": "A paragraph (2-5 sentences) summarizing key events/decisions/topics. "
                        "Start with [YYYY-MM-DD HH:MM]. Include detail useful for grep search.",
                    },
                    # memory_update 是完整的长期记忆 markdown，写入 MEMORY.md
                    "memory_update": {
                        "type": "string",
                        "description": "Full updated long-term memory as markdown. Include all existing "
                        "facts plus new ones. Return unchanged if nothing new.",
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


class MemoryStore:
    """
    MemoryStore 负责管理 nanobot 的长期记忆和历史日志。
    - MEMORY.md：长期记忆，结构化 markdown，内容会被注入到每次对话的 prompt。
    - HISTORY.md：历史日志，记录每次记忆整合的关键信息，便于全文检索和回溯。
    """

    def __init__(self, workspace: Path):
        # 初始化记忆目录和文件路径，确保 memory 目录存在
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"  # 长期记忆文件
        self.history_file = self.memory_dir / "HISTORY.md"  # 历史日志文件

    def read_long_term(self) -> str:
        # 读取 MEMORY.md 的全部内容，作为长期记忆注入 prompt
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        # 覆盖写入 MEMORY.md，保存最新的长期记忆内容。 是覆盖，而不是追加
        # 里保存的内容可以包括用户画像信息，比如性别、偏好、习惯、长期事实等。
        self.memory_file.write_text(content, encoding="utf-8")

    # 主要场景是将历史作为检索 / 回溯用的日志，而不是频繁读取和注入到prompt。
    # 长期记忆（MEMORY.md）才会被每次对话注入，历史日志仅用于人工查阅或后续检索。
    # 目前业务流程没有需要自动读取和处理全部历史记录的需求。
    # 如果后续需要支持历史检索、分析或上下文增强，可以新增读取 HISTORY.md 的方法。
    def append_history(self, entry: str) -> None:
        # 追加一条历史记录到 HISTORY.md，每次记忆整合后调用
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        # 获取长期记忆内容，供 prompt 注入
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""



    """
           Function 介绍
           记忆整合主流程：
           1. 判断是否需要整合（如消息数超阈值、主动归档等）。
           2. 整理需要归档的旧消息，格式化为文本，供 LLM 总结。
           3. 构造 prompt，包含当前长期记忆和本次需整合的对话。
           4. 调用 LLM（function calling），要求其用 save_memory 工具返回：
              - history_entry：写入 HISTORY.md，便于全文检索
              - memory_update：写入 MEMORY.md，作为下次 prompt 注入的长期记忆
           5. 更新会话整合进度。
           返回 True 表示整合成功或无需整合，False 表示失败。
    """
    async def consolidate(
        self,
        session: Session,  # 当前会话对象，包含消息列表和整合进度
        provider: LLMProvider,  # LLMProvider 实例，用于调用大语言模型
        model: str,  # 指定使用的 LLM 模型名称或标识
        *,
        archive_all: bool = False,  # 是否强制整合所有消息（True 时归档全部）
        memory_window: int = 50,    # 记忆窗口大小，用于判断保留多少最新消息不归档
    ) -> bool:
        if archive_all:
            # 主动归档所有消息：
            #“主动归档所有消息”指的是在记忆整合时，不做筛选，直接将当前会话中的所有消息都作为需要整合的对象进行归档和总结。通常用于需要强制保存全部历史内容的场景，比如用户手动触发归档或系统定期全量归档。
            # 这里的“会话”指的是你和大模型之间反复沟通的全过程，比如你在一段时间不断讨论和修改数仓表结构。最后让大模型进行归档，就是对这段会话的消息进行提取、总结和归纳，形成简明的历史记录和长期记忆，便于后续查阅和检索。
            old_messages = session.messages #就不做筛选，直接把当前会话里的所有消息都作为需要整合的对象进行归档和总结，常用于用户手动触发或系统定期全量归档的场景。这样可以确保所有历史内容都被保存和总结，不会遗漏。
            keep_count = 0
            logger.info("Memory consolidation (archive_all): {} messages", len(session.messages))
        else:
            keep_count = memory_window // 2
            #场景举例：你和大模型反复讨论一个需求，产生了 60 条消息。现在要做记忆整合，但希望最近的 25 条消息暂时不归档（因为可能还在持续讨论，内容还会变化），只把更早的消息归档总结。
            # 消息数量不够，无需整合
            if len(session.messages) <= keep_count:
                return True
            # 没有新消息需要整合
            if len(session.messages) - session.last_consolidated <= 0:
                return True
            # 取出需要整合的旧消息（不包括最新 keep_count 条）
            old_messages = session.messages[session.last_consolidated:-keep_count]
            if not old_messages:
                return True
            logger.info("Memory consolidation: {} to consolidate, {} keep", len(old_messages), keep_count)

        # 格式化旧消息为文本，供 LLM 处理
        # 这段代码的作用是：把需要整合的旧消息（old_messages）格式化成结构化的文本列表，每条消息包含时间、角色、工具信息（如有）和内容。
        # 这样整理后，便于后续拼接成大段文本，供大语言模型（LLM）进行总结和归档处理。没有内容的消息会被跳过。最终得到的 lines 列表，就是一条条可读性强、便于检索的消息记录。
        lines = []
        for m in old_messages:
            if not m.get("content"):
                continue
            # 标注工具调用信息，便于后续检索
            tools = f" [tools: {', '.join(m['tools_used'])}]" if m.get("tools_used") else ""  ## 格式化成字符串 [tools: 工具1, 工具2]
            lines.append(f"[{m.get('timestamp', '?')[:16]}] {m['role'].upper()}{tools}: {m['content']}")

        current_memory = self.read_long_term()
        # 构造 prompt，包含当前长期记忆和本次需整合的对话
        prompt = f"""Process this conversation and call the save_memory tool with your consolidation.\n\n## Current Long-term Memory\n{current_memory or "(empty)"}\n\n## Conversation to Process\n{chr(10).join(lines)}"""

        try:
            # 调用 LLM，要求其用 save_memory 工具返回整合结果
            response = await provider.chat(
                messages=[
                    ## 这句话告诉 LLM：你现在的身份不是聊天机器人，而是记忆整合专家。你的唯一任务就是调用 save_memory 这个工具
                    {"role": "system", "content": "You are a memory consolidation agent. Call the save_memory tool with your consolidation of the conversation."},
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_MEMORY_TOOL,
                model=model,
            )

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory, skipping")
                return False

            args = response.tool_calls[0].arguments
            # 某些 provider 返回字符串，需要反序列化
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                logger.warning("Memory consolidation: unexpected arguments type {}", type(args).__name__)
                return False

            # 写入历史和长期记忆
            if entry := args.get("history_entry"):
                if not isinstance(entry, str):
                    entry = json.dumps(entry, ensure_ascii=False)
                self.append_history(entry)  # 追加到 HISTORY.md
            if update := args.get("memory_update"):
                if not isinstance(update, str):
                    update = json.dumps(update, ensure_ascii=False)
                if update != current_memory:
                    self.write_long_term(update)  # 覆盖写入 MEMORY.md

            # 更新会话整合进度，避免重复整合
            session.last_consolidated = 0 if archive_all else len(session.messages) - keep_count
            logger.info("Memory consolidation done: {} messages, last_consolidated={}", len(session.messages), session.last_consolidated)
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return False
