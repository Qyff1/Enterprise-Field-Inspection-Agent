"""
MCP (Model Context Protocol) 服务模块
在此文件中定义和注册你的 MCP 服务连接。
MCP 服务用于扩展 Agent 的能力，例如连接外部数据源、API 等。
"""
from langchain_mcp_adapters.client import MultiServerMCPClient
import asyncio
import os
import threading
from typing import Optional, Dict, Any

# ============================================================
# MCP 服务注册表 - 在此添加你的 MCP 服务
# ============================================================
# 每个 MCP 服务需要一个唯一的名称和连接配置
# 后端会自动读取此列表并通过 API 暴露给前端

MCP_SERVICES = [
    # --- 高德MCP服务---
    {
        "name": "amap-maps",
        "display_name": "高德服务",
        "description": "获取地址和导航",
        "enabled": True,
        "config": {
            "transport": "streamable_http",
            "url": "https://mcp.amap.com/mcp",
            "api_key": os.getenv("AMAP_API_KEY", "")
        }
    },

]


def get_enabled_mcp_services() -> list:
    """返回所有已启用的 MCP 服务列表（供前端展示）"""
    return [s for s in MCP_SERVICES if s.get("enabled", False)]


def get_all_mcp_services() -> list:
    """返回所有 MCP 服务列表（供管理界面使用）"""
    return MCP_SERVICES


def initialize_mcp_services():
    """
    初始化所有已启用的MCP服务并返回合并后的工具列表
    供 model.py 调用以绑定到agent
    """
    enabled_services = get_enabled_mcp_services()
    if not enabled_services:
        return []

    client_config = {}
    for service in enabled_services:
        config = service["config"]
        api_key = config.get("api_key", "")
        url = config["url"]
        if api_key:
            url = f"{url}?key={api_key}"

        client_config[service["name"]] = {
            "transport": config["transport"],
            "url": url
        }

    async def _get_all_tools():
        client = MultiServerMCPClient(client_config)
        try:
            tools = await client.get_tools()
            return tools
        except Exception as e:
            print(f"获取MCP工具时发生错误: {e}")
            return []

    try:
        return asyncio.run(_get_all_tools())
    except Exception as e:
        print(f"MCP服务初始化失败: {e}")
        return []


# ============================================================
# MCP 工具桥接 - 供自定义工具函数调用高德 MCP
# ============================================================

def get_mcp_tool_map() -> Dict[str, Any]:
    """
    返回 {tool_name: tool_object} 字典
    供 geocode_address、calculate_route_mileage 等自定义工具
    直接调用已绑定的高德 MCP 工具
    """
    from agents.tools import TOOLS
    return {t.name: t for t in TOOLS if hasattr(t, 'name')}


def call_mcp_tool(tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    同步调用 MCP 工具（在自定义 @tool 函数中使用）

    Args:
        tool_name: MCP 工具名称，如 "maps-geocode"
        **kwargs: 传递给 MCP 工具的参数

    Returns:
        MCP 工具返回的结果字典，失败返回 None
    """
    tool_map = get_mcp_tool_map()
    tool = tool_map.get(tool_name)
    if tool is None:
        print(f"[MCP Bridge] 工具 '{tool_name}' 未找到，可用工具: {list(tool_map.keys())}")
        return None

    async def _invoke():
        try:
            result = await tool.ainvoke(kwargs)
            return result
        except Exception as e:
            print(f"[MCP Bridge] 调用 '{tool_name}' 失败: {e}")
            return None

    try:
        # 尝试获取当前运行中的事件循环
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            # 在已有事件循环中运行（Flask 异步上下文）
            return asyncio.run_coroutine_threadsafe(_invoke(), loop).result(timeout=30)
        else:
            return asyncio.run(_invoke())
    except Exception as e:
        print(f"[MCP Bridge] 异步调用 '{tool_name}' 异常: {e}")
        return None


def get_amap_api_key() -> str:
    """获取高德 API Key"""
    for svc in MCP_SERVICES:
        if svc.get("name") == "amap-maps":
            return svc.get("config", {}).get("api_key", "")
    return os.getenv("AMAP_API_KEY", "")