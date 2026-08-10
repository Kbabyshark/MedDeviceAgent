"""
Summary Memory 服务 — 长对话摘要压缩。

触发条件：
- Token 估计值超过 4000
- 对话轮数超过 15 轮

使用 DeepSeek-V3 生成摘要。
"""

from __future__ import annotations

from app.core.llm import ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)

# 触发阈值
TRIGGER_TOKENS = 4000
TRIGGER_ROUNDS = 15

# 每次摘要保留最近 N 条消息不被摘要
_KEEP_RECENT = 4


def estimate_tokens(messages: list) -> int:
    """粗略估计消息的 Token 数（中文约 1.5 字符/token）。"""
    total = 0
    for msg in messages:
        content = ""
        if isinstance(msg, dict):
            content = msg.get("content", "")
        elif hasattr(msg, "content"):
            content = msg.content
        total += len(str(content)) // 1.5
    return int(total)


class SummaryService:
    """对话摘要服务。

    使用方式：
        svc = SummaryService()
        if svc.should_summarize(messages):
            summary = await svc.summarize(messages)
            await svc.save(user_id, session_id, summary, version)
    """

    def should_summarize(self, messages: list, current_tokens: int | None = None) -> bool:
        """判断是否需要触发摘要。"""
        if len(messages) > TRIGGER_ROUNDS:
            return True

        tokens = current_tokens or estimate_tokens(messages)
        if tokens > TRIGGER_TOKENS:
            return True

        return False

    def get_messages_to_summarize(self, messages: list) -> tuple[list, list]:
        """拆分消息：需要摘要的部分 + 保留的部分。

        Returns:
            (to_summarize, keep_recent): 待摘要的消息，保留的最近消息
        """
        if len(messages) <= _KEEP_RECENT:
            return [], messages

        to_summarize = messages[:-_KEEP_RECENT]
        keep_recent = messages[-_KEEP_RECENT:]
        return to_summarize, keep_recent

    async def summarize(self, messages: list) -> str:
        """对消息列表生成摘要。

        使用 DeepSeek-V3 + summary prompt。
        Mock 模式返回规则摘要。
        """
        if not messages:
            return ""

        # 转为文本格式
        msg_text = _format_messages(messages)

        llm = get_llm_client()

        if llm.mock_mode:
            return self._mock_summarize(messages)

        try:
            pm = get_prompt_manager()
            template = pm.get("summary", "v1")
            system, user_prompt = template.render(messages=msg_text)

            result = await llm.chat(
                prompt=user_prompt,
                system=system,
                model=ModelType.V3,
                temperature=0.3,
                max_tokens=512,
            )

            logger.info("summary_generated", msg_count=len(messages), summary_len=len(result.content))
            return result.content.strip()

        except Exception as e:
            logger.error("summary_generate_error", error=str(e))
            return self._mock_summarize(messages)

    def _mock_summarize(self, messages: list) -> str:
        """Mock 模式：提取首尾主题生成规则摘要。"""
        if not messages:
            return ""

        first = ""
        last = ""
        for msg in messages:
            content = msg.get("content", "") if isinstance(msg, dict) else getattr(msg, "content", "")
            if content and not first:
                first = content[:100]
            if content:
                last = content[:100]

        return f"[摘要] 用户咨询了: {first}... → 最后讨论了: {last}... (共 {len(messages)} 条消息)"

    async def save(
        self,
        user_id: str,
        session_id: str,
        summary: str,
        version: int = 1,
    ) -> None:
        """保存摘要到 MySQL conversation_summary 表。"""
        import asyncio

        def _save():
            import pymysql
            from datetime import datetime
            from app.core.config import get_settings
            s = get_settings().mysql
            conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                                   password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO conversation_summary (user_id, session_id, summary, version, created_at) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (int(user_id), session_id, summary, version, datetime.now()),
                )
                conn.commit()
            finally:
                conn.close()

        try:
            await asyncio.to_thread(_save)
            logger.info("summary_saved", user_id=user_id, session_id=session_id, version=version, len=len(summary))
        except Exception as e:
            logger.error("summary_save_failed", error=str(e))


def _format_messages(messages: list) -> str:
    """格式化消息列表为文本。"""
    lines = []
    for msg in messages:
        role = ""
        content = ""
        if isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
        elif hasattr(msg, "content"):
            role = getattr(msg, "role", "unknown")
            content = msg.content
        lines.append(f"[{role}]: {str(content)[:300]}")
    return "\n".join(lines)
