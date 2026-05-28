# 企业外勤核验智能Agent

> 🚀 基于大语言模型的智能对话 Agent，集成多工具调度、MCP 服务、RAG 知识库和外勤行程核验等能力

<p align="center">
  <a href="#功能特性">功能特性</a> •
  <a href="#技术栈">技术栈</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#外勤核验流程">外勤核验流程</a> •
  <a href="#API文档">API 文档</a>
</p>

---

## ✨ 功能特性

### 核心能力
- **🔍 多工具调度**: 集成网页搜索、高德地图（地理编码 + 路线规划）、文件读写等 12 个工具
- **📋 外勤行程核验**: 四阶段审计流水线（文档解析 → 地理校验 → 异常检测 → 报告生成）
- **🔗 MCP 协议**: 通过 Model Context Protocol 连接高德地图 MCP 服务
- **📚 RAG 知识库**: 基于 ChromaDB 的向量检索引擎，支持语义搜索
- **⚡ Skills 技能系统**: 可扩展的 Markdown 技能定义，按需触发
- **💬 流式对话**: SSE (Server-Sent Events) 实时推送 Agent 思考与工具调用过程

### 外勤核验特色
- **自动化解析**: 支持 Word/Excel/CSV/Text 多种格式的外勤报告
- **地理编码**: 高德地图地址标准化与坐标转换
- **里程校验**: 申报里程与真实路线自动比对
- **异常检测**: 时间冲突、里程偏差、地址异常等多维度检测
- **历史分析**: 基于员工历史出行模式的智能判断
- **专业报告**: 结构化审计报告生成

---

## 🛠️ 技术栈

| 分类 | 技术 | 说明 |
|------|------|------|
| Web 框架 | Flask + Flask-CORS | 轻量级后端服务 |
| LLM | DashScope (Qwen) | 阿里云大模型，兼容 OpenAI API |
| Agent 框架 | LangChain + LangGraph | 智能体编排与状态管理 |
| 向量数据库 | ChromaDB | RAG 语义检索引擎 |
| MCP 协议 | langchain-mcp-adapters | 高德地图服务集成 |
| 文档解析 | python-docx + openpyxl | Word/Excel 文档处理 |
| 前端 | 原生 HTML/CSS/JS | 简洁的流式交互界面 |

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip 22.0+

### 安装步骤

```bash
# 1. 克隆项目
git clone <your-repo-url>
cd 企业外勤核查agent

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 API 密钥（见下方配置说明）

# 3. 初始化对话记忆（可选，使用示例数据）
cp data/memory.example.md data/memory.md

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动服务
python app.py
```

启动成功后访问：`http://localhost:5000`

---

## 🔑 API 密钥配置

编辑 `.env` 文件，填入以下密钥：

| 密钥 | 必填 | 说明 | 获取地址 |
|------|------|------|----------|
| `API_KEY` | ✅ 是 | DashScope API Key | [DashScope 控制台](https://dashscope.console.aliyun.com/) |
| `AMAP_API_KEY` | ✅ 是 | 高德地图 API | [高德开放平台](https://lbs.amap.com/) |
| `BOCHA_API_KEY` | ❌ 否 | Bocha 网页搜索 API | [Bocha API](https://api.bochaai.com/) |

> **说明**：
> - `API_KEY`：所有功能必需
> - `AMAP_API_KEY`：外勤核验核心功能必需（地理编码、路线规划、里程校验）
> - `BOCHA_API_KEY`：仅用于网络搜索，本地知识库优先

### 配置示例
```env
# DashScope (阿里云) API - 必填
API_KEY=sk-your-dashscope-api-key-here
BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_NAME=qwen3.6-plus
MAX_TOKENS=1000
TEMPERATURE=0.7

# Bocha Web Search API - 可选
BOCHA_API_KEY=sk-your-bocha-api-key-here

# 高德地图 API - 可选
AMAP_API_KEY=your-amap-api-key-here
```

---

## 📋 外勤核验流程

### 四阶段审计流水线

```
┌─────────────────────────────────────────────────────────┐
│  1. 文档解析                                             │
│     - 解析 Word/Excel/CSV/Text 文档                      │
│     - 提取结构化行程记录（员工、日期、路线、里程等）    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  2. 地理校验                                             │
│     - 地址标准化（高德地图 API）                          │
│     - 坐标转换与经纬度计算                                │
│     - 规划路线并获取真实里程                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  3. 异常检测                                             │
│     - 里程偏差分析（绿色/黄色/红色阈值）                  │
│     - 时间冲突检测（同一天重叠行程）                      │
│     - 历史模式对比（常规地点判定）                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│  4. 报告生成                                             │
│     - 结构化审计报告                                      │
│     - 风险等级评定                                        │
│     - 详细异常说明与建议                                  │
└─────────────────────────────────────────────────────────┘
```

### 企业规则配置

项目内置了通用的企业外勤核验规则（`data/knowledge.md`），包括：

- 里程偏差阈值（绿色≤5%、黄色5%-15%、红色>15%）
- 时间冲突判定（间隔<30分钟）
- 常规地点判定（≥3次历史访问）
- 常用城市间里程参考

企业可根据自身需求修改 `data/knowledge.md` 自定义规则。

---

## 📡 API 文档

### 会话管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/create_session` | POST | 创建新会话 |
| `/api/clear_session` | POST | 清空会话 |

### 聊天

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 普通聊天 |
| `/api/chat/stream` | POST | 流式聊天 (SSE) |

### 信息查询

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/tools` | GET | 工具列表 |
| `/api/mcp_services` | GET | MCP 服务列表 |
| `/api/skills` | GET | 技能列表 |
| `/api/model_info` | GET | 模型配置 |
| `/api/knowledge` | GET | 知识库条目 |
| `/api/knowledge/reindex` | POST | 重建索引 |

### 其他

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/upload_file` | POST | 文件上传 (≤50MB) |
| `/api/save_conversation` | POST | 保存对话 |

---

## 📂 项目结构

```
企业外勤核查agent/
├── app.py                  # Flask 主入口
├── config.py               # 配置加载
├── requirements.txt        # Python 依赖
├── .env.example            # 环境变量模板
├── .gitignore              # Git 忽略文件
├── agents/                 # Agent 核心模块
│   ├── model.py            # LLM 初始化
│   ├── chat.py             # 多会话管理器
│   ├── tools.py            # 工具定义（12+ 工具）
│   ├── prompt.py           # 系统提示词
│   ├── rag.py              # RAG 知识库（ChromaDB）
│   ├── skills.py           # 技能系统
│   └── mcp_services.py     # MCP 服务注册
├── skills/                 # 技能定义文件 (.md)
│   ├── document-parser.md  # 文档解析技能
│   ├── geo-verifier.md     # 地理校验技能
│   ├── anomaly-detector.md # 异常检测技能
│   └── ...
├── data/                   # 知识库与记忆（示例）
│   ├── knowledge.md        # 企业规则知识库
│   ├── memory.example.md   # 对话记忆模板
│   └── test_trip_report.docx # 测试文档
├── static/                 # 前端静态资源
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
└── storage/                # 运行时数据（不提交）
    ├── uploads/            # 上传文件
    ├── outputs/            # 输出报告
    └── chromadb/           # 向量数据库
```

---

## 🔧 扩展开发

### 添加新工具

在 `agents/tools.py` 中：

```python
from langchain.tools import tool

@tool
def my_tool(param: str) -> str:
    """工具描述（这会被 Agent 看到）"""
    # 工具实现逻辑
    return "结果"

# 添加到工具列表
TOOLS.append(my_tool)
```

### 添加新技能

在 `skills/` 目录下创建 `.md` 文件，定义触发词和功能说明。示例格式见 `skills/` 目录。

### 添加 MCP 服务

在 `agents/mcp_services.py` 的 `MCP_SERVICES` 列表中添加配置。

---

## 🚀 部署

### 开发环境
```bash
python app.py
```

### 生产环境 (Gunicorn)
```bash
pip install gunicorn
gunicorn --workers=4 --bind=0.0.0.0:5000 app:app
```

### Docker 部署（可选）
建议创建 Dockerfile 实现容器化部署。

---

## ❓ 常见问题

### 启动问题
- **启动失败**: 确认已安装所有依赖 `pip install -r requirements.txt`
- **模块缺失**: Python 版本低于 3.10 会导致部分模块不可用

### API 问题
- **API 限流错误**: DashScope 免费版 QPS 较低，等待几秒后重试或升级配额
- **地理编码失败**: 检查 AMAP_API_KEY 是否正确配置

### 功能问题
- **文件上传失败**: 确认文件类型在白名单内，大小不超过 50MB
- **知识库检索无结果**: 调用 `/api/knowledge/reindex` 重建索引
- **MCP 服务不可用**: 降级到 REST API 模式，不影响核心功能

---

## 📜 License

MIT

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 🙏 致谢

- [DashScope (阿里云)](https://dashscope.aliyun.com/) - 大模型服务
- [高德开放平台](https://lbs.amap.com/) - 地图服务
- [LangChain](https://www.langchain.com/) - Agent 框架
- [ChromaDB](https://www.trychroma.com/) - 向量数据库

