"""
聊天管理器 - 管理多会话对话
每个会话拥有独立的对话历史
支持 Skills 技能自动检测与触发
"""

import asyncio
import logging
from typing import Dict, List, Optional

from agents.model import agent
from agents.prompt import SYSTEM_PROMPT
from agents.skills import detect_skill, get_skill_prompt
from config import load_api_config

logger = logging.getLogger(__name__)
api_config = load_api_config(model_type='openai')

# 与 QPS 限流相关的错误关键词
_RATE_LIMIT_KEYWORDS = [
    'CUQPS', 'QPS', 'exceeded', 'limit', 'rate',
    'throttle', 'quota', 'too many requests', '429',
]


def _is_rate_limit_error(error: Exception) -> bool:
    """判断异常是否为 QPS 限流错误"""
    error_str = str(error).lower()
    return any(kw.lower() in error_str for kw in _RATE_LIMIT_KEYWORDS)


class RateLimitError(Exception):
    """QPS 限流异常（重试耗尽后抛出）"""
    pass


class ChatManager:
    """多会话聊天管理器"""

    def __init__(self):
        self._conversations: Dict[str, List[Dict]] = {}
        self._max_retries = api_config['max_retries']
        self._retry_delay = api_config['retry_delay']

    # ---- 会话生命周期管理 ----

    def create_conversation(self, conversation_id: str) -> None:
        """创建新会话，初始化对话历史"""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = []

    def clear_conversation(self, conversation_id: str) -> None:
        """清空会话的对话历史"""
        if conversation_id in self._conversations:
            self._conversations[conversation_id] = []

    def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """获取会话的对话历史"""
        return self._conversations.get(conversation_id, [])

    # ---- 对话处理 ----

    async def chat(self, conversation_id: str, user_input: str) -> str:
        """
        处理用户输入并返回 AI 回复（含 QPS 限流重试）
        自动检测 Skills 触发关键词并应用对应的系统提示词
        """
        if conversation_id not in self._conversations:
            self.create_conversation(conversation_id)

        # 记录用户原始消息
        self._add_message(conversation_id, "user", user_input)

        # 构建消息列表（包含 skill 提示词注入）
        state_messages = self._build_messages_with_skill(conversation_id, user_input)

        # 带指数退避的重试调用
        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await agent.ainvoke({"messages": state_messages})
                ai_response = response["messages"][-1].content

                # 记录 AI 回复
                self._add_message(conversation_id, "assistant", ai_response)
                return ai_response

            except Exception as e:
                last_error = e
                if _is_rate_limit_error(e) and attempt < self._max_retries:
                    wait_time = self._retry_delay * (2 ** attempt)
                    logger.warning(
                        f"QPS 限流 (尝试 {attempt + 1}/{self._max_retries + 1})，"
                        f"{wait_time:.1f}s 后重试..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    break

        # 所有重试都失败，抛出明确的错误
        if _is_rate_limit_error(last_error):
            raise RateLimitError(
                f"API 调用频率超限（已重试 {self._max_retries} 次）。"
                f"请稍等几秒后重试，或升级 DashScope API 的 QPS 配额。"
                f"\n原始错误: {last_error}"
            )
        raise last_error

    def _build_messages_with_skill(self, conversation_id: str, user_input: str) -> List[Dict]:
        """
        构建消息列表，自动检测 Skills 并将技能提示词注入到用户消息中
        """
        state_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self._conversations[conversation_id]
        ]

        # 检测用户消息是否触发了某个 Skill
        matched_skill = detect_skill(user_input)
        if matched_skill:
            skill_prompt = get_skill_prompt(matched_skill)
            if skill_prompt:
                # 将 skill 提示词注入到最后一条用户消息的前面
                last_msg = state_messages[-1]
                if last_msg["role"] == "user":
                    last_msg["content"] = (
                        f"[系统指令 - {matched_skill['display_name']}]\n"
                        f"{skill_prompt}\n\n"
                        f"---\n"
                        f"用户消息: {last_msg['content']}"
                    )

        return state_messages

    # ---- 内部方法 ----

    def _add_message(self, conversation_id: str, role: str, content: str) -> None:
        """向会话历史中添加一条消息"""
        self._conversations[conversation_id].append({
            "role": role,
            "content": content
        })
