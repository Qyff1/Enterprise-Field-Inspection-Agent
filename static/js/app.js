// ============================================================
        // 配置 & 全局状态
        // ============================================================
        var API_BASE = '/api';
        var sessionId = null;
        var attachedFiles = [];  // 待上传的文件列表
        var currentStreamAbort = null;  // 当前流式请求的 AbortController

        // ============================================================
        // 侧边栏选项卡切换
        // ============================================================
        document.querySelectorAll('.sidebar-tab').forEach(function(tab) {
            tab.addEventListener('click', function() {
                // 切换选项卡激活状态
                document.querySelectorAll('.sidebar-tab').forEach(function(t) { t.classList.remove('active'); });
                this.classList.add('active');
                // 切换面板显示
                document.querySelectorAll('.sidebar-panel').forEach(function(p) { p.classList.remove('active'); });
                document.getElementById(this.dataset.panel).classList.add('active');
            });
        });

        // ============================================================
        // 会话管理
        // ============================================================
        async function createSession() {
            try {
                var resp = await axios.post(API_BASE + '/create_session');
                sessionId = resp.data.session_id;
                console.log('会话已创建:', sessionId);
            } catch (e) {
                console.error('创建会话失败:', e);
                sessionId = 'local_' + Date.now();
            }
        }

        async function clearSession() {
            // 先提示保存
            var messagesDiv = document.getElementById('messages');
            var msgElements = messagesDiv.querySelectorAll('.message');
            if (msgElements.length > 0) {
                var doSave = confirm('是否将当前对话保存到 memory.md 后再清空？\n\n点击"确定"保存并清空，"取消"仅清空不保存。');
                if (doSave) {
                    await doSaveConversation();
                }
            }

            // 清空消息区
            messagesDiv.innerHTML = '<div class="welcome-message" id="welcome">' +
                '<div class="welcome-icon">🗑</div>' +
                '<div class="welcome-text">会话已清空，有什么需要帮助的吗？</div>' +
                '</div>';

            if (sessionId) {
                try {
                    await axios.post(API_BASE + '/clear_session', { session_id: sessionId });
                } catch (e) {
                    console.error('清空会话失败:', e);
                }
            }
        }

        /** 收集当前对话中的所有消息 */
        function collectMessages() {
            var messages = [];
            var messagesDiv = document.getElementById('messages');
            var msgElements = messagesDiv.querySelectorAll('.message');
            msgElements.forEach(function(el) {
                var role = el.classList.contains('user') ? 'user' : 'assistant';
                var contentDiv = el.querySelector('.message-content');
                if (contentDiv) {
                    var text = contentDiv.textContent || contentDiv.innerText || '';
                    if (text.trim()) {
                        messages.push({ role: role, content: text.trim() });
                    }
                }
            });
            return messages;
        }

        /** 执行对话保存 */
        async function doSaveConversation() {
            var messages = collectMessages();
            if (messages.length === 0) return false;

            try {
                var resp = await axios.post(API_BASE + '/save_conversation', {
                    session_id: sessionId,
                    messages: messages
                });
                if (resp.data.success) {
                    console.log('[Memory] 对话已保存');
                    return true;
                }
            } catch (e) {
                console.error('[Memory] 保存失败:', e);
            }
            return false;
        }

        /** 保存对话按钮点击 */
        async function saveConversation() {
            var messages = collectMessages();
            if (messages.length === 0) {
                alert('当前对话为空，无需保存');
                return;
            }
            var ok = await doSaveConversation();
            if (ok) {
                // 临时显示保存成功提示
                showToolStatus('💾 对话已保存到 memory.md');
                setTimeout(hideToolStatus, 2500);
            } else {
                alert('保存失败，请检查后端服务是否正常运行');
            }
        }

        // ============================================================
        // 文件处理功能
        // ============================================================

        /** 格式化文件大小 */
        function formatFileSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
        }

        /** 根据文件扩展名返回图标 */
        function getFileIcon(name) {
            var ext = name.split('.').pop().toLowerCase();
            var iconMap = {
                jpg: '🖼', jpeg: '🖼', png: '🖼', gif: '🖼', webp: '🖼', bmp: '🖼', svg: '🖼',
                docx: '📝', pdf: '📄', xlsx: '📊', pptx: '📽',
                txt: '📃', md: '📃', json: '📋', csv: '📊',
                py: '💻', js: '💻', html: '💻', css: '💻', log: '📃',
                zip: '📦', rar: '📦', '7z': '📦'
            };
            return iconMap[ext] || '📎';
        }

        /** 添加文件到预览区 */
        function addFilePreview(file) {
            attachedFiles.push(file);
            renderFilePreviews();
        }

        /** 移除预览区文件 */
        function removeFilePreview(index) {
            attachedFiles.splice(index, 1);
            renderFilePreviews();
        }

        /** 渲染文件预览区 */
        function renderFilePreviews() {
            var container = document.getElementById('filePreview');
            container.innerHTML = '';

            if (attachedFiles.length === 0) {
                container.classList.remove('has-files');
                return;
            }

            container.classList.add('has-files');
            attachedFiles.forEach(function(file, i) {
                var item = document.createElement('div');
                item.className = 'file-preview-item';
                item.innerHTML =
                    '<span class="file-icon">' + getFileIcon(file.name) + '</span>' +
                    '<div class="file-info">' +
                    '<div class="file-name" title="' + escapeHtml(file.name) + '">' + escapeHtml(file.name) + '</div>' +
                    '<div class="file-size">' + formatFileSize(file.size) + '</div>' +
                    '</div>' +
                    '<button class="file-remove" onclick="removeFilePreview(' + i + ')" title="移除">✕</button>';
                container.appendChild(item);
            });
        }

        /** 清空文件预览 */
        function clearAttachedFiles() {
            attachedFiles = [];
            renderFilePreviews();
        }

        /** 处理文件选择（点击附件按钮） */
        function handleFileSelect(event) {
            var files = event.target.files;
            for (var i = 0; i < files.length; i++) {
                addFilePreview(files[i]);
            }
            event.target.value = '';
        }

        // ============================================================
        // 拖拽上传事件处理
        // ============================================================
        var dropCounter = 0;

        document.addEventListener('dragenter', function(e) {
            e.preventDefault();
            dropCounter++;
            if (dropCounter === 1) {
                document.getElementById('dropOverlay').classList.add('active');
            }
        });

        document.addEventListener('dragleave', function(e) {
            dropCounter--;
            if (dropCounter <= 0) {
                document.getElementById('dropOverlay').classList.remove('active');
                dropCounter = 0;
            }
        });

        document.addEventListener('dragover', function(e) {
            e.preventDefault();
        });

        document.addEventListener('drop', function(e) {
            e.preventDefault();
            dropCounter = 0;
            document.getElementById('dropOverlay').classList.remove('active');

            var files = e.dataTransfer.files;
            for (var i = 0; i < files.length; i++) {
                addFilePreview(files[i]);
            }
        });

        // 粘贴图片支持
        document.addEventListener('paste', function(e) {
            var items = e.clipboardData && e.clipboardData.items;
            if (!items) return;

            for (var i = 0; i < items.length; i++) {
                if (items[i].kind === 'file') {
                    var file = items[i].getAsFile();
                    if (file) addFilePreview(file);
                }
            }
        });

        // 附件按钮点击
        document.getElementById('attachBtn').addEventListener('click', function() {
            document.getElementById('fileInput').click();
        });

        // ============================================================
        // 聊天功能（流式 + 文件上传）
        // ============================================================

        /** 上传文件到服务器，返回文件路径列表 */
        async function uploadAttachedFiles() {
            var paths = [];
            for (var i = 0; i < attachedFiles.length; i++) {
                var file = attachedFiles[i];
                var formData = new FormData();
                formData.append('file', file);

                try {
                    var resp = await axios.post(API_BASE + '/upload_file', formData, {
                        headers: { 'Content-Type': 'multipart/form-data' }
                    });
                    if (resp.data.success) {
                        paths.push(resp.data.file_path);
                    }
                } catch (e) {
                    var errMsg = e.response && e.response.data && e.response.data.error
                        ? e.response.data.error : '上传失败';
                    console.error('文件上传失败:', file.name, errMsg);
                    addMessage('assistant', '文件上传失败 [' + file.name + ']: ' + errMsg, true);
                }
            }
            clearAttachedFiles();
            return paths;
        }

        async function sendMessage(event) {
            event.preventDefault();
            var input = document.getElementById('messageInput');
            var message = input.value.trim();
            if (!message || !sessionId) return;

            // 如果有附件，先上传
            var filePaths = [];
            if (attachedFiles.length > 0) {
                filePaths = await uploadAttachedFiles();
            }

            // 构建带文件路径的消息
            var fullMessage = message;
            if (filePaths.length > 0) {
                fullMessage = message + '\n[用户上传的文件路径: ' + filePaths.join(', ') + ']';
            }

            // 显示用户消息
            addMessage('user', message);
            input.value = '';
            setLoading(true);

            // 使用流式请求
            await sendMessageStream(fullMessage);
        }

        /** 流式发送消息并接收 SSE 响应 */
        async function sendMessageStream(message) {
            // 取消之前的流式请求
            if (currentStreamAbort) {
                currentStreamAbort.abort();
            }
            currentStreamAbort = new AbortController();

            var responseDiv = null;   // 回复消息容器
            var responseText = '';    // 累积的回复文本
            var currentTool = null;   // 当前正在执行的工具

            try {
                var response = await fetch(API_BASE + '/chat/stream', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, message: message }),
                    signal: currentStreamAbort.signal
                });

                if (!response.ok) {
                    var errData = await response.json().catch(function() { return {}; });
                    throw new Error(errData.error || '请求失败 (HTTP ' + response.status + ')');
                }

                var reader = response.body.getReader();
                var decoder = new TextDecoder();
                var buffer = '';

                while (true) {
                    var result = await reader.read();
                    var done = result.done;
                    var value = result.value;

                    if (value) {
                        buffer += decoder.decode(value, { stream: true });
                    }

                    var lines = buffer.split('\n');
                    buffer = lines.pop() || '';

                    for (var i = 0; i < lines.length; i++) {
                        var line = lines[i];
                        if (line.startsWith('data: ')) {
                            try {
                                var data = JSON.parse(line.slice(6));
                                switch (data.type) {
                                    case 'status':
                                        if (data.content === 'thinking') {
                                            showToolStatus('Agent 正在思考...');
                                        } else if (data.content === 'tool_call') {
                                            currentTool = data.tool;
                                            showToolStatus('正在调用工具: ' + data.tool + ' ...');
                                        } else if (data.content === 'tool_done') {
                                            currentTool = null;
                                            showToolStatus('工具 ' + data.tool + ' 执行完成，继续思考...');
                                        } else if (data.content === 'skill_triggered') {
                                            showToolStatus('已触发技能: ' + (data.skill || ''));
                                            setTimeout(hideToolStatus, 2000);
                                        }
                                        break;

                                    case 'response':
                                        if (!responseDiv) {
                                            removeLoading();
                                            responseDiv = createAssistantMessageDiv();
                                        }
                                        hideToolStatus();
                                        responseText += data.content;
                                        responseDiv.querySelector('.message-content').innerHTML = renderMarkdown(responseText);
                                        scrollToBottom();
                                        break;

                                    case 'error':
                                        removeLoading();
                                        hideToolStatus();
                                        addMessage('assistant', '错误: ' + data.content, true);
                                        break;

                                    case 'done':
                                        if (!responseDiv && responseText) {
                                            removeLoading();
                                            responseDiv = createAssistantMessageDiv();
                                            responseDiv.querySelector('.message-content').innerHTML = renderMarkdown(responseText);
                                        }
                                        hideToolStatus();
                                        break;
                                }
                            } catch (parseErr) {
                                // 跳过解析失败的行
                            }
                        }
                    }

                    if (done) break;
                }
            } catch (e) {
                if (e.name === 'AbortError') {
                    console.log('流式请求已取消');
                    return;
                }
                removeLoading();
                hideToolStatus();
                var errMsg = e.message || '抱歉，发生了未知错误';
                addMessage('assistant', errMsg, true);
            }

            setLoading(false);
            currentStreamAbort = null;
        }

        /** 创建 assistant 消息容器，返回 DOM 元素 */
        function createAssistantMessageDiv() {
            var messagesDiv = document.getElementById('messages');
            var msgDiv = document.createElement('div');
            msgDiv.className = 'message assistant';
            msgDiv.id = 'streaming-response';

            var contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.innerHTML = '';

            msgDiv.appendChild(contentDiv);
            messagesDiv.appendChild(msgDiv);
            return msgDiv;
        }

        /** 显示工具状态栏 */
        function showToolStatus(text) {
            var bar = document.getElementById('toolStatus');
            var textEl = document.getElementById('toolStatusText');
            textEl.textContent = text;
            bar.classList.add('visible');
        }

        /** 隐藏工具状态栏 */
        function hideToolStatus() {
            var bar = document.getElementById('toolStatus');
            bar.classList.remove('visible');
        }

        /**
         * 在消息区域添加一条消息
         * @param {string} role  - 'user' | 'assistant'
         * @param {string} content - 消息内容
         * @param {boolean} isError - 是否为错误消息
         */
        function addMessage(role, content, isError) {
            var messagesDiv = document.getElementById('messages');
            var welcome = document.getElementById('welcome');
            if (welcome) welcome.remove();

            var msgDiv = document.createElement('div');
            msgDiv.className = 'message ' + role;

            var contentDiv = document.createElement('div');
            contentDiv.className = 'message-content' + (isError ? ' error' : '');

            // 用户消息直接显示原文，AI 消息使用 Markdown 渲染
            if (role === 'assistant' && !isError) {
                contentDiv.innerHTML = renderMarkdown(content);
            } else {
                contentDiv.textContent = content;
            }

            msgDiv.appendChild(contentDiv);
            messagesDiv.appendChild(msgDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        /** 滚动到底部 */
        function scrollToBottom() {
            var messagesDiv = document.getElementById('messages');
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        /** 切换输入区域加载状态 */
        function setLoading(loading) {
            var btn = document.getElementById('sendBtn');
            var input = document.getElementById('messageInput');
            btn.disabled = loading;
            input.disabled = loading;

            if (loading) {
                removeLoading();
                var messagesDiv = document.getElementById('messages');
                var loadDiv = document.createElement('div');
                loadDiv.className = 'message assistant';
                loadDiv.id = 'loading-msg';
                loadDiv.innerHTML = '<div class="message-content"><div class="loading-dots"><span></span><span></span><span></span></div></div>';
                messagesDiv.appendChild(loadDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            } else {
                removeLoading();
                // 移除流式响应的 id 标记（使其成为普通消息）
                var streamDiv = document.getElementById('streaming-response');
                if (streamDiv) streamDiv.removeAttribute('id');
            }
        }

        /** 移除加载动画 */
        function removeLoading() {
            var el = document.getElementById('loading-msg');
            if (el) el.remove();
        }

        // Enter 发送
        document.getElementById('messageInput').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage(e);
            }
        });

        // ============================================================
        // 侧边栏数据加载
        // ============================================================

        /** 加载工具列表 */
        async function loadTools() {
            var container = document.getElementById('tools-list');
            try {
                var resp = await axios.get(API_BASE + '/tools');
                var tools = resp.data.tools || [];

                if (tools.length === 0) {
                    container.innerHTML = '<div class="empty-state">' +
                        '<div class="icon">🔧</div>' +
                        '<div class="text">暂无已注册的工具<br>请在 <code>agents/tools.py</code> 中添加</div>' +
                        '</div>';
                    return;
                }

                var html = '';
                tools.forEach(function(t) {
                    html += '<div class="panel-card">' +
                        '<div class="card-name">' + escapeHtml(t.name) + '</div>' +
                        '<div class="card-desc">' + escapeHtml(t.description) + '</div>' +
                        '<div class="card-meta">参数: ' + escapeHtml(JSON.stringify(t.args_schema).substring(0, 100)) + '...</div>' +
                        '</div>';
                });
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="empty-state"><div class="text">加载失败: ' + escapeHtml(e.message) + '</div></div>';
            }
        }

        /** 加载 MCP 服务列表 */
        async function loadMcpServices() {
            var container = document.getElementById('mcp-list');
            try {
                var resp = await axios.get(API_BASE + '/mcp_services');
                var services = resp.data.mcp_services || [];

                if (services.length === 0) {
                    // 显示占位示例，提示用户在何处添加 MCP 服务
                    container.innerHTML =
                        '<div class="placeholder-hint">' +
                        '<p>暂无 MCP 服务配置</p>' +
                        '<p style="margin-top:8px;">请在 <code>agents/mcp_services.py</code><br>的 <code>MCP_SERVICES</code> 列表中<br>添加你的 MCP 服务</p>' +
                        '</div>' +
                        '<div style="margin-top:12px;">' +
                        renderMcpExample() +
                        '</div>';
                    return;
                }

                var html = '';
                services.forEach(function(s) {
                    var badgeClass = s.enabled ? 'enabled' : 'disabled';
                    var badgeText = s.enabled ? '已启用' : '已禁用';
                    html += '<div class="panel-card">' +
                        '<div class="card-name">' + escapeHtml(s.display_name || s.name) +
                        ' <span class="status-badge ' + badgeClass + '">' + badgeText + '</span></div>' +
                        '<div class="card-desc">' + escapeHtml(s.description || '无描述') + '</div>' +
                        '<div class="card-meta">类型: ' + escapeHtml((s.config && s.config.type) || 'unknown') + '</div>' +
                        '</div>';
                });
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="empty-state"><div class="text">加载失败: ' + escapeHtml(e.message) + '</div></div>';
            }
        }

        /** 渲染 MCP 示例卡片（前端预留展示） */
        function renderMcpExample() {
            return '<div class="panel-card" style="opacity:0.6;">' +
                '<div class="card-name">📁 文件系统 <span class="status-badge placeholder">示例</span></div>' +
                '<div class="card-desc">读取和写入本地文件（MCP 服务示例）</div>' +
                '<div class="card-meta">类型: stdio | 状态: 待配置</div>' +
                '</div>' +
                '<div class="panel-card" style="opacity:0.6;">' +
                '<div class="card-name">🗄 PostgreSQL <span class="status-badge placeholder">示例</span></div>' +
                '<div class="card-desc">查询 PostgreSQL 数据库（MCP 服务示例）</div>' +
                '<div class="card-meta">类型: stdio | 状态: 待配置</div>' +
                '</div>';
        }

        /** 加载 Skills 列表 */
        async function loadSkills() {
            var container = document.getElementById('skills-list');
            try {
                var resp = await axios.get(API_BASE + '/skills');
                var skills = resp.data.skills || [];

                if (skills.length === 0) {
                    container.innerHTML =
                        '<div class="placeholder-hint">' +
                        '<p>暂无 Skills 配置</p>' +
                        '<p style="margin-top:8px;">请在 <code>agents/skills.py</code><br>的 <code>SKILLS</code> 列表中<br>添加你的 Skills</p>' +
                        '</div>' +
                        '<div style="margin-top:12px;">' +
                        renderSkillsExample() +
                        '</div>';
                    return;
                }

                var html = '';
                skills.forEach(function(s) {
                    var badgeClass = s.enabled ? 'enabled' : 'disabled';
                    var badgeText = s.enabled ? '已启用' : '已禁用';
                    html += '<div class="panel-card">' +
                        '<div class="card-name">' + escapeHtml(s.display_name || s.name) +
                        ' <span class="status-badge ' + badgeClass + '">' + badgeText + '</span></div>' +
                        '<div class="card-desc">' + escapeHtml(s.description || '无描述') + '</div>' +
                        '<div class="card-meta">触发词: ' + escapeHtml((s.trigger_keywords || []).join(', ') || '无') + '</div>' +
                        '</div>';
                });
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="empty-state"><div class="text">加载失败: ' + escapeHtml(e.message) + '</div></div>';
            }
        }

        /** 渲染 Skills 示例卡片（前端预留展示） */
        function renderSkillsExample() {
            return '<div class="panel-card" style="opacity:0.6;">' +
                '<div class="card-name">📝 代码审查 <span class="status-badge placeholder">示例</span></div>' +
                '<div class="card-desc">对提供的代码进行审查，检查安全问题、代码风格和潜在 bug</div>' +
                '<div class="card-meta">触发词: 审查, review, 检查代码 | 状态: 待配置</div>' +
                '</div>' +
                '<div class="panel-card" style="opacity:0.6;">' +
                '<div class="card-name">📊 数据分析 <span class="status-badge placeholder">示例</span></div>' +
                '<div class="card-desc">对上传的数据文件进行分析并生成可视化报告</div>' +
                '<div class="card-meta">触发词: 分析数据, 数据报告 | 状态: 待配置</div>' +
                '</div>';
        }

        /** 加载知识库条目 */
        async function loadKnowledge() {
            var container = document.getElementById('knowledge-list');
            try {
                var resp = await axios.get(API_BASE + '/knowledge');
                var entries = resp.data.entries || [];
                var rag = resp.data.rag || {};

                // RAG 状态栏
                var ragStatusHtml = '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;padding:8px 12px;background:rgba(100,255,218,0.05);border-radius:6px;font-size:0.8rem;">' +
                    '<span>🔍 RAG: <span style="color:' + (rag.total_indexed > 0 ? '#64ffda' : '#ffc107') + ';">' +
                    (rag.total_indexed > 0 ? '已索引 ' + rag.total_indexed + ' 条' : rag.status || '未初始化') +
                    '</span></span>' +
                    '<button onclick="reindexKnowledge()" style="padding:3px 8px;font-size:0.7rem;background:transparent;border:1px solid #0f3460;color:#8892b0;border-radius:4px;cursor:pointer;" title="重建向量索引">🔄 重建索引</button>' +
                    '</div>';

                if (entries.length === 0) {
                    container.innerHTML = ragStatusHtml +
                        '<div class="placeholder-hint">' +
                        '<p>📚 知识库为空</p>' +
                        '<p style="margin-top:8px;">请在 <code>knowledge.md</code> 中添加知识条目</p>' +
                        '<p style="margin-top:4px;font-size:0.8rem;">格式参见文件中的示例</p>' +
                        '</div>' +
                        '<div style="margin-top:12px;">' + renderKnowledgeExample() + '</div>';
                    return;
                }

                // 按分类分组
                var categories = {};
                entries.forEach(function(e) {
                    if (!categories[e.category]) categories[e.category] = [];
                    categories[e.category].push(e);
                });

                var html = ragStatusHtml;
                Object.keys(categories).forEach(function(cat) {
                    html += '<div style="color:#64ffda;font-size:0.8rem;font-weight:600;margin:10px 0 6px 0;">📁 ' + escapeHtml(cat) + '</div>';
                    entries.filter(function(e) { return e.category === cat; }).forEach(function(e) {
                        var tagsHtml = (e.tags || '').split(',').map(function(t) {
                            return '<span style="display:inline-block;background:rgba(100,255,218,0.1);color:#64ffda;padding:1px 6px;border-radius:8px;font-size:0.7rem;margin:2px;">' + escapeHtml(t.trim()) + '</span>';
                        }).join('');
                        html += '<div class="panel-card">' +
                            '<div class="card-name">' + escapeHtml(e.title) + '</div>' +
                            '<div class="card-desc">' + escapeHtml(e.content.substring(0, 150)) + (e.content.length > 150 ? '...' : '') + '</div>' +
                            '<div class="card-meta">' + tagsHtml + ' | 更新: ' + escapeHtml(e.updated) + '</div>' +
                            '</div>';
                    });
                });
                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<div class="empty-state"><div class="text">加载失败: ' + escapeHtml(e.message) + '</div></div>';
            }
        }

        /** 重建 RAG 向量索引 */
        async function reindexKnowledge() {
            var btn = event.target;
            btn.disabled = true;
            btn.textContent = '⏳ 索引中...';
            try {
                var resp = await axios.post(API_BASE + '/knowledge/reindex');
                if (resp.data.success) {
                    showToolStatus('✅ 索引重建完成: 知识库 ' + resp.data.knowledge_count + ' 条, 记忆 ' + resp.data.memory_count + ' 条');
                    setTimeout(hideToolStatus, 3000);
                    loadKnowledge(); // 刷新面板
                } else {
                    alert('索引重建失败: ' + (resp.data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + (e.message || '网络错误'));
            }
            btn.disabled = false;
            btn.textContent = '🔄 重建索引';
        }

        /** 渲染知识库示例 */
        function renderKnowledgeExample() {
            return '<div class="panel-card" style="opacity:0.6;">' +
                '<div class="card-name">📝 Python 虚拟环境 <span class="status-badge placeholder">示例</span></div>' +
                '<div class="card-desc">使用 python -m venv .venv 创建虚拟环境...</div>' +
                '<div class="card-meta">标签: Python, venv | 更新: 2026-01-15</div>' +
                '</div>';
        }

        /** 加载模型信息 */
        async function loadModelInfo() {
            var container = document.getElementById('model-info');
            try {
                var resp = await axios.get(API_BASE + '/model_info');
                var info = resp.data;

                container.innerHTML =
                    '<div class="panel-card">' +
                    '<div class="card-name">当前模型</div>' +
                    '<div class="card-desc" style="font-size:1rem;color:#e0e0e0;">' + escapeHtml(info.model_name) + '</div>' +
                    '</div>' +
                    '<div class="panel-card">' +
                    '<div class="card-name">API 地址</div>' +
                    '<div class="card-desc" style="font-size:0.8rem;">' + escapeHtml(info.base_url) + '</div>' +
                    '</div>' +
                    '<div class="panel-card">' +
                    '<div class="card-name">参数配置</div>' +
                    '<div class="card-desc">' +
                    'Max Tokens: ' + info.max_tokens + '<br>' +
                    'Temperature: ' + info.temperature + '<br>' +
                    'Provider: ' + escapeHtml(info.provider) +
                    '</div>' +
                    '</div>';
            } catch (e) {
                container.innerHTML = '<div class="empty-state"><div class="text">加载失败: ' + escapeHtml(e.message) + '</div></div>';
            }
        }

        /** HTML 转义，防止 XSS */
        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        /** 简易 Markdown → HTML 转换（安全子集） */
        function renderMarkdown(text) {
            if (!text) return '';

            // 转义 HTML
            var html = escapeHtml(text);

            // 代码块 (```...```)
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(m, lang, code) {
                return '<pre><code>' + code + '</code></pre>';
            });

            // 行内代码 (`...`)
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

            // 标题
            html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

            // 水平线
            html = html.replace(/^---$/gm, '<hr>');

            // 引用
            html = html.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');

            // 无序列表项
            html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');

            // 将连续的 <li> 包裹在 <ul> 中
            html = html.replace(/(<li>.*?<\/li>)(?:\s*<br>\s*)?/g, function(m) {
                return m;
            });
            // 合并连续的 <li>（处理 <br> 分隔的情况）
            html = html.replace(/(?:<li>.*?<\/li>(?:<br>)?)+/g, function(m) {
                // 移除尾随 <br>
                var inner = m.replace(/<br>$/, '');
                return '<ul>' + inner + '</ul>';
            });

            // 粗体和斜体
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

            // 段落：双换行分段
            html = html.replace(/\n\n/g, '</p><p>');
            html = html.replace(/\n/g, '<br>');

            // 包裹段落
            if (html.indexOf('<p>') !== 0 && html.indexOf('<h') !== 0 && html.indexOf('<ul>') !== 0 &&
                html.indexOf('<pre>') !== 0 && html.indexOf('<blockquote>') !== 0 && html.indexOf('<hr>') !== 0) {
                html = '<p>' + html + '</p>';
            }

            return html;
        }


        // ============================================================
        // 页面关闭时自动保存
        // ============================================================
        var hasUnsavedMessages = false;

        // 监听消息变化，标记为未保存
        var messagesObserver = new MutationObserver(function() {
            var msgElements = document.getElementById('messages').querySelectorAll('.message');
            if (msgElements.length > 0) {
                hasUnsavedMessages = true;
            }
        });
        messagesObserver.observe(document.getElementById('messages'), {
            childList: true, subtree: true
        });

        // 页面关闭/刷新时尝试保存
        window.addEventListener('beforeunload', function(e) {
            if (!hasUnsavedMessages) return;

            var messages = collectMessages();
            if (messages.length === 0) return;

            // 使用 sendBeacon 确保关闭期间请求能发出
            var payload = JSON.stringify({
                session_id: sessionId,
                messages: messages
            });
            navigator.sendBeacon(API_BASE + '/save_conversation', new Blob([payload], {
                type: 'application/json'
            }));

            // Chrome 需要设置 returnValue 才能触发确认对话框
            // 由于 sendBeacon 是异步且可靠的，不阻塞用户离开
            hasUnsavedMessages = false;
        });

        // ============================================================
        // 初始化
        // ============================================================
        async function init() {
            await createSession();
            loadTools();
            loadMcpServices();
            loadSkills();
            loadKnowledge();
            loadModelInfo();
        }

        init();

        // ============================================================
        // 外勤核验快捷操作
        // ============================================================

        /** 保存对话按钮 */
        async function saveConversation() {
            var msgs = collectMessages();
            if (msgs.length === 0) {
                alert('当前对话为空，无需保存');
                return;
            }
            try {
                var resp = await axios.post(API_BASE + '/save_conversation', {
                    session_id: sessionId,
                    messages: msgs
                });
                if (resp.data.success) {
                    showToolStatus('对话已保存到 memory.md');
                    setTimeout(hideToolStatus, 2000);
                }
            } catch (e) {
                alert('保存失败: ' + (e.message || '网络错误'));
            }
        }

        /** 一键外勤核验快捷入口 */
        function quickAudit() {
            var filePreview = document.getElementById('filePreview');
            var hasFiles = filePreview && filePreview.children.length > 0;

            var input = document.getElementById('messageInput');
            if (hasFiles) {
                input.value = '审核这份外勤报告，执行全流程核验并生成审计报告';
            } else {
                input.value = '请先上传外勤报告文件（.docx/.xlsx），然后我来审核';
            }
            input.focus();

            // 如果有文件，自动发送
            if (hasFiles && input.value) {
                sendMessage(new Event('submit'));
            }
        }