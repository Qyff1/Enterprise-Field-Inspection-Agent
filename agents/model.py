"""
LLM 模型初始化模块
使用 LangChain 的 ChatOpenAI 兼容接口连接 DashScope (阿里云) 的 Qwen 模型
"""

import time
import logging
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from openai import RateLimitError, APIStatusError

from config import load_api_config
from agents.prompt import SYSTEM_PROMPT
from agents.tools import TOOLS
from agents.mcp_services import initialize_mcp_services

logger = logging.getLogger(__name__)

# 初始化MCP服务并合并工具
try:
    mcp_tools = initialize_mcp_services()
    if mcp_tools:
        TOOLS.extend(mcp_tools)
        print(f"MCP工具加载成功，已绑定 {len(mcp_tools)} 个工具到agent")
    else:
        print("MCP服务未返回工具，agent仅使用基础工具")
except Exception as e:
    print(f"MCP服务初始化失败: {e}")

# 加载 API 配置
api_config = load_api_config(model_type='openai')

# 初始化 LLM 实例（含重试和限流处理）
llm = ChatOpenAI(
    model=api_config['model_name'],
    api_key=api_config['api_key'],
    base_url=api_config['base_url'],
    max_tokens=api_config['max_tokens'],
    timeout=api_config['timeout'],
    temperature=api_config['temperature'],
    streaming=True,
    max_retries=api_config['max_retries'],
    request_timeout=api_config['timeout'],
)


def _create_summarization_middleware():
    """
    创建对话摘要中间件
    当上下文超过 1000 tokens 时自动压缩历史消息，保留最近 2 条完整消息
    """
    return SummarizationMiddleware(
        model=llm,
        trigger=("tokens", 2500),
        keep=("messages", 2)
    )


# 创建 Agent 实例（全局单例，所有会话共享）
agent = create_agent(
    model=llm,
    tools=TOOLS,
    middleware=[_create_summarization_middleware()],
    system_prompt=SYSTEM_PROMPT
)

# ---- RAG 知识库初始化 ----
try:
    from agents.rag import init_rag
    rag_stats = init_rag()
    print(f"RAG 知识库已索引: knowledge={rag_stats.get('knowledge', 0)} 条, memory={rag_stats.get('memory', 0)} 条")
except Exception as e:
    print(f"RAG 初始化失败（可忽略，将回退到文件读取方式）: {e}")