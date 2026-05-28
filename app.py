"""
Flask 主应用 - 企业外勤核验智能Agent后端
提供前端页面服务和 REST API 接口
"""

from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import json
import time
import uuid
import queue
import threading

from agents.chat import ChatManager, RateLimitError
from agents.tools import TOOLS, get_tools_metadata
from agents.mcp_services import get_all_mcp_services
from agents.skills import get_all_skills, detect_skill
from agents.model import agent
import asyncio

from config import load_api_config

app = Flask(__name__, static_folder='static')
CORS(app)

# 初始化聊天管理器
chat_manager = ChatManager()

# ============================================================
# 文件上传配置
# ============================================================
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'storage', 'uploads')
ALLOWED_EXTENSIONS = {
    'txt', 'md', 'json', 'csv', 'py', 'log', 'html', 'xml', 'yaml', 'yml',
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg',
    'docx', 'pdf', 'xlsx', 'pptx'
}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename: str) -> bool:
    """检查文件扩展名是否在允许列表中"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# 页面路由
# ============================================================

@app.route('/')
def index():
    """返回前端主页面"""
    return send_file('static/index.html')


# ============================================================
# 会话管理 API

# ============================================================

@app.route('/api/create_session', methods=['POST'])
def create_session():
    """创建新的对话会话，返回 session_id"""
    session_id = str(uuid.uuid4())
    chat_manager.create_conversation(session_id)
    return jsonify({'session_id': session_id})


@app.route('/api/clear_session', methods=['POST'])
def clear_session():
    """清空指定会话的对话历史"""
    data = request.json or {}
    session_id = data.get('session_id')
    if session_id:
        chat_manager.clear_conversation(session_id)
    return jsonify({'success': True})


# ============================================================
# 聊天 API
# ============================================================

@app.route('/api/chat', methods=['POST'])
def chat():
    """
    发送消息并获取 AI 回复
    请求体: { "session_id": "...", "message": "..." }
    响应:   { "response": "..." }
    """
    data = request.json or {}
    session_id = data.get('session_id')
    message = data.get('message')

    if not session_id or not message:
        return jsonify({'error': '缺少必要参数 session_id 或 message'}), 400

    try:
        response = asyncio.run(chat_manager.chat(session_id, message))
        return jsonify({'response': response})
    except RateLimitError as e:
        return jsonify({'error': str(e), 'retry_after': '请稍等几秒后重试'}), 429
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# 工具 / MCP / Skills 信息 API（供前端面板展示）
# ============================================================

@app.route('/api/tools', methods=['GET'])
def list_tools():
    """返回所有已注册的工具列表及其元数据"""
    try:
        tools_meta = get_tools_metadata()
        return jsonify({'tools': tools_meta, 'total': len(tools_meta)})
    except Exception as e:
        return jsonify({'error': str(e), 'tools': []}), 500


@app.route('/api/mcp_services', methods=['GET'])
def list_mcp_services():
    """返回所有 MCP 服务配置列表"""
    try:
        services = get_all_mcp_services()
        return jsonify({'mcp_services': services, 'total': len(services)})
    except Exception as e:
        return jsonify({'error': str(e), 'mcp_services': []}), 500


@app.route('/api/skills', methods=['GET'])
def list_skills():
    """返回所有 Skills 配置列表"""
    try:
        skills = get_all_skills()
        return jsonify({'skills': skills, 'total': len(skills)})
    except Exception as e:
        return jsonify({'error': str(e), 'skills': []}), 500


@app.route('/api/model_info', methods=['GET'])
def model_info():
    """返回当前使用的模型配置信息（隐藏敏感信息）"""
    try:
        config = load_api_config('openai')
        return jsonify({
            'model_name': config.get('model_name', 'unknown'),
            'base_url': config.get('base_url', 'unknown'),
            'max_tokens': config.get('max_tokens', 0),
            'temperature': config.get('temperature', 0),
            'provider': 'openai-compatible'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================
# 文件上传 API
# ============================================================

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    """
    上传文件接口，支持拖拽上传
    返回服务器端文件路径供 read_local_file 工具使用
    """
    if 'file' not in request.files:
        return jsonify({'error': '没有找到文件'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '文件名为空'}), 400

    if not allowed_file(file.filename):
        return jsonify({'error': f'不支持的文件类型，支持: {", ".join(sorted(ALLOWED_EXTENSIONS))}'}), 400

    # 检查文件大小
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': f'文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)'}), 400

    filename = secure_filename(file.filename)
    # 添加时间戳避免文件名冲突
    unique_filename = f"{int(time.time() * 1000)}_{filename}"
    filepath = os.path.join(UPLOAD_FOLDER, unique_filename)
    file.save(filepath)

    suffix = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    return jsonify({
        'success': True,
        'file_path': filepath,
        'file_name': filename,
        'file_size': file_size,
        'file_type': suffix,
    })


# ============================================================
# 知识库 API
# ============================================================

@app.route('/api/knowledge', methods=['GET'])
def list_knowledge():
    """解析 knowledge.md 并返回结构化知识条目列表"""
    import re

    knowledge_path = os.path.join(os.path.dirname(__file__), 'data', 'knowledge.md')
    if not os.path.exists(knowledge_path):
        return jsonify({'entries': [], 'total': 0})

    try:
        with open(knowledge_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return jsonify({'error': str(e), 'entries': []}), 500

    # 解析知识条目: ### [分类] 标题\n- **标签**: ...\n- **内容**: ...\n- **来源**: ...\n- **更新**: ...
    entries = []
    pattern = r'###\s*\[([^\]]+)\]\s*(.+?)\n- \*\*标签\*\*:\s*(.+?)\n- \*\*内容\*\*:\s*([\s\S]*?)(?:\n- \*\*来源\*\*:\s*(.+?))?\n- \*\*更新\*\*:\s*(.+?)\n'
    for match in re.finditer(pattern, content):
        entries.append({
            'category': match.group(1).strip(),
            'title': match.group(2).strip(),
            'tags': match.group(3).strip(),
            'content': match.group(4).strip().replace('\n- ', '\n'),
            'source': match.group(5).strip() if match.group(5) else '未知',
            'updated': match.group(6).strip(),
        })

    # 附加 RAG 状态
    rag_status = {}
    try:
        from agents.rag import get_rag
        rag = get_rag()
        rag_status = rag.get_stats()
    except Exception:
        rag_status = {'status': '未初始化', 'total_indexed': 0}

    return jsonify({'entries': entries, 'total': len(entries), 'rag': rag_status})


@app.route('/api/knowledge/reindex', methods=['POST'])
def reindex_knowledge():
    """强制重建 RAG 向量索引"""
    try:
        from agents.rag import init_rag
        stats = init_rag(force=True)
        return jsonify({
            'success': True,
            'message': '索引重建完成',
            'knowledge_count': stats.get('knowledge', 0),
            'memory_count': stats.get('memory', 0),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# 对话保存 API
# ============================================================

@app.route('/api/save_conversation', methods=['POST'])
def save_conversation():
    """
    保存当前对话摘要到 memory.md
    请求体: { "session_id": "...", "messages": [...] }
    """
    from datetime import datetime

    data = request.json or {}
    session_id = data.get('session_id', '')
    messages = data.get('messages', [])

    if not messages:
        return jsonify({'success': False, 'error': '对话内容为空'}), 400

    # 构建对话摘要
    summary_parts = []
    for msg in messages:
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')
        # 截断过长的内容
        if len(content) > 300:
            content = content[:300] + '...'
        summary_parts.append(f"[{role}] {content}")

    conversation_text = '\n'.join(summary_parts)
    date_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    # 写入 memory.md
    memory_path = os.path.join(os.path.dirname(__file__), 'data', 'memory.md')
    entry = (
        f"\n### [{datetime.now().strftime('%Y-%m-%d')}] 对话记录 - {date_str}\n"
        f"- **类型**: 对话存档\n"
        f"- **时间**: {date_str}\n"
        f"- **会话ID**: {session_id}\n"
        f"- **内容**:\n"
        f"```\n{conversation_text}\n```\n"
    )

    try:
        with open(memory_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        return jsonify({'success': True, 'message': '对话已保存到 memory.md'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================
# 流式聊天 API (SSE)
# ============================================================

@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """
    流式聊天接口，使用 Server-Sent Events 实时推送 Agent 响应
    事件类型:
      - status:  状态更新 (thinking / tool_call / tool_done)
      - response: AI 回复内容
      - error:    错误信息
      - done:     流结束
    """
    data = request.json or {}
    session_id = data.get('session_id')
    message = data.get('message')

    if not session_id or not message:
        return jsonify({'error': '缺少必要参数 session_id 或 message'}), 400

    def generate():
        q = queue.Queue()
        loop = asyncio.new_event_loop()

        async def stream_agent():
            # QPS 限流检测函数（内联，避免跨模块依赖）
            def _is_qps_error(err):
                err_str = str(err).lower()
                return any(kw in err_str for kw in [
                    'cuqps', 'qps', 'exceeded', 'rate', 'throttle', 'quota', 'too many requests'
                ])

            try:
                # 确保会话存在
                if session_id not in chat_manager._conversations:
                    chat_manager.create_conversation(session_id)

                # 记录用户消息
                chat_manager._add_message(session_id, "user", message)

                # 构建消息列表（含 Skill 提示词注入）
                state_messages = chat_manager._build_messages_with_skill(session_id, message)

                # 发送 Skill 触发状态通知
                matched_skill = detect_skill(message)
                if matched_skill:
                    q.put(sse_event('status', {
                        'content': 'skill_triggered',
                        'skill': matched_skill['display_name'],
                        'text': f'已触发技能: {matched_skill["display_name"]}'
                    }))

                # 发送开始状态
                q.put(sse_event('status', {'content': 'thinking', 'text': 'Agent 正在思考...'}))

                full_response = ""

                # QPS 限流重试循环
                max_retries = 3
                retry_delay = 2.0
                last_error = None

                for attempt in range(max_retries + 1):
                    try:
                        async for chunk in agent.astream(
                            {"messages": state_messages},
                            stream_mode="updates"
                        ):
                            for node_name, node_output in chunk.items():
                                if node_output is None:
                                    continue
                                messages_out = node_output.get("messages", [])
                                for msg in messages_out:
                                    if msg is None:
                                        continue
                                    msg_type = getattr(msg, 'type', 'unknown')

                                    if msg_type == 'ai':
                                        tool_calls = getattr(msg, 'tool_calls', None)
                                        if tool_calls:
                                            for tc in tool_calls:
                                                if tc is None:
                                                    continue
                                                tc_name = tc.get('name', 'unknown') if isinstance(tc, dict) else getattr(tc, 'name', 'unknown')
                                                q.put(sse_event('status', {
                                                    'content': 'tool_call',
                                                    'tool': tc_name,
                                                    'text': f'正在调用工具: {tc_name}'
                                                }))
                                        else:
                                            content = getattr(msg, 'content', '')
                                            if content:
                                                content_str = content if isinstance(content, str) else str(content)
                                                full_response += content_str
                                                q.put(sse_event('response', {'content': content_str}))

                                    elif msg_type == 'tool':
                                        tool_name = getattr(msg, 'name', 'unknown')
                                        q.put(sse_event('status', {
                                            'content': 'tool_done',
                                            'tool': tool_name,
                                            'text': f'工具 {tool_name} 执行完成'
                                        }))
                        break  # 成功，退出重试循环

                    except Exception as e:
                        last_error = e
                        if _is_qps_error(e) and attempt < max_retries:
                            wait_time = retry_delay * (2 ** attempt)
                            q.put(sse_event('status', {
                                'content': 'retry',
                                'text': f'API 限流，{wait_time:.0f}s 后重试 (第{attempt + 1}/{max_retries}次)...'
                            }))
                            await asyncio.sleep(wait_time)
                        else:
                            break

                # 所有重试耗尽
                if last_error and _is_qps_error(last_error):
                    q.put(sse_event('error', {
                        'content': f'API 调用频率超限，请稍等几秒后重试。\n原始错误: {last_error}'
                    }))
                elif last_error:
                    q.put(sse_event('error', {'content': str(last_error)}))

                # 记录 AI 完整回复
                if full_response:
                    chat_manager._add_message(session_id, "assistant", full_response)

                q.put(sse_event('done', {}))

            except Exception as e:
                q.put(sse_event('error', {'content': str(e)}))
            finally:
                q.put(None)  # 结束信号

        def run_async():
            asyncio.set_event_loop(loop)
            loop.run_until_complete(stream_agent())

        t = threading.Thread(target=run_async, daemon=True)
        t.start()

        while True:
            try:
                item = q.get(timeout=300)  # 5 分钟超时
                if item is None:
                    break
                yield item
            except queue.Empty:
                break

        t.join(timeout=5)
        loop.close()

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        }
    )


def sse_event(event_type: str, data: dict) -> str:
    """构建 SSE 格式的事件数据"""
    payload = json.dumps({**data, 'type': event_type}, ensure_ascii=False)
    return f"data: {payload}\n\n"


# ============================================================
# 启动入口
# ============================================================

if __name__ == '__main__':
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    print('=' * 50)
    print('  企业外勤核验智能Agent服务已启动')
    print('  前端地址: http://localhost:5000')
    print('  Debug 模式:', '开启' if debug_mode else '关闭')
    print('=' * 50)
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)