# MedDeviceAgent — 医疗设备智能客服 Agent 平台

基于 **FastAPI + LangGraph** 构建的面向医疗设备售后场景的企业级 Agent 系统。通过 **RAG 混合检索、Tool Calling 工具执行、Human-in-the-loop 用户确认、Guardrails 安全审查、全链路 Trace 可观测** 五大能力，实现可控、可追踪、可评估的智能客服 Workflow。

## 核心业务能力

| 能力 | 说明 |
|------|------|
| 设备知识问答 | 产品说明书 RAG 检索与智能回答 |
| FAQ 查询 | 常见问题快速匹配 |
| 故障码解释 | 设备错误码精确查询与解释 |
| 故障排查 | 多轮对话式故障诊断引导 |
| 保修查询 | 设备保修状态与到期查询 |
| 设备绑定查询 | 用户-设备关系查询 |
| 创建维修工单 | 含 Human-in-the-loop 确认流程 |
| 转人工 | 对话摘要同步 + 排队等待 |
| 医疗高风险拦截 | 五类风险输入/输出双端安全检测 |

---

## 技术栈

| 层级 | 技术 |
|------|------|
| **Web 框架** | FastAPI + Vue3 |
| **数据验证** | Pydantic v2 |
| **ORM** | SQLAlchemy 2.x (async) + Alembic |
| **Agent 编排** | LangGraph (StateGraph + Checkpoint) |
| **RAG** | Embedding + Hybrid Retrieval (Qdrant 向量 + BM25 关键词) + RRF 融合 + Rerank |
| **向量数据库** | Qdrant |
| **缓存 / 锁** | Redis (分布式锁、限流、Session 缓存) |
| **数据库** | MySQL 8.0 |
| **异步任务** | Celery (Redis Broker) |
| **对象存储** | MinIO |
| **前端** | Vue 3 + Naive UI + Pinia + TailwindCSS |
| **认证** | JWT (python-jose + bcrypt) |
| **可观测** | LangSmith 全链路追踪 + structlog 日志 + 内置告警系统 |

---

## 系统架构

### Agent Workflow（16 节点）

```
User Input
  ↓
Input Safety Check ──(high risk)──→ Safe Reply
  ↓
Intent Classification (AC 自动机规则 + LLM 兜底)
  ↓
Context Load (设备信息 + 长短期记忆 + 对话摘要)
  ↓
Query Router ──→ fault_code_lookup
  │                 ↓
  ├──→ query_rewrite → rag_retrieve → rag_rerank → rag_answer
  │                                                    ↓
  ├──→ tool_execute ──(需确认)──→ Human Confirm ──→ Execute Tool
  │                                                    ↓
  └──→ safe_reply ──────────────────────────────────→
                                                       ↓
                                              Answer Generate
                                                       ↓
                                             Output Safety Check
                                                       ↓
                                                Memory Update
                                                       ↓
                                                   Response
```

整个 Workflow 基于 `State → Node → Edge` 有向图编排，所有节点通过 `AgentState` 显式通信，禁止全局变量和隐式传递。支持非流式与 SSE 流式两种响应模式，单会话支持多轮对话中断恢复。

---

### 意图识别与路由

采用 **规则优先 + LLM 兜底** 的两层架构：

- **AC 自动机规则层**：预置 13 组中文关键词规则，覆盖保修查询、报修工单、转人工、故障码、设备绑定、FAQ、售后政策、医疗风险词、闲聊等 12 种意图。规则命中时按次数 + 关键词长度加权 + 写操作额外加权排序，多意图场景返回排序列表供下游路由决策。
- **LLM 兜底层**：规则未命中时走 LLM 结构化分类，输出 `{intent, confidence}` JSON，降低模型调用成本和前置延迟。
- **路由分发**：RAG 检索 / Tool 执行 / Fault Code 精确查询 / Safe Reply 四条路径。

### Hybrid RAG 检索管线

```
用户查询 → Query Rewrite
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
Vector 检索          BM25 关键词检索
(Qdrant + BGE)       (SQLite FTS5 + jieba)
    ↓                   ↓
    └─────────┬─────────┘
              ↓
         RRF 融合
              ↓
         Rerank 重排序
              ↓
         答案生成
```

- **Metadata 过滤**：device_type / doc_type / permission 三级过滤，禁止无过滤条件全库搜索
- **无结果降级**：严格过滤 → 放宽 device_type → Query Rewrite 重试 → 提示转人工
- **BM25 索引**：基于 SQLite FTS5 + jieba 分词，写入时自动增量追加
- **文档解析后处理**：集成 MinerU 解析 PDF 输出 Markdown，目录块自动检测与删除、页眉页脚频率统计过滤、页码/URL/版权符号等噪声清理；通过 pdfplumber 提取每页锚点注入 `[Page N]` 位置标记，保证 Chunk 页码可追溯
- **Chunk → Embedding → Qdrant**：文档切分后由 Celery 异步做 Embedding 批量写入 Qdrant

### Tool Calling + Human-in-the-loop

5 个业务工具通过 Tool Registry 统一注册，LLM 仅生成调用意图，实际执行经过完整链路：

```
LLM 生成 Tool Intent → Schema Validation → Permission Check → Risk Check → Human Confirm → Tool Execute
```

| Tool | 功能 | 风险等级 | 需确认 |
|------|------|----------|--------|
| `query_warranty` | 查询保修状态 | 低 | 否 |
| `query_device_binding` | 查询设备绑定 | 低 | 否 |
| `create_ticket` | 创建维修工单 | 高 | 是 |
| `create_warranty` | 登记设备保修 | 中 | 是 |
| `transfer_human` | 转人工 | 高 | 是 |

高风险写操作通过 LangGraph `interrupt` 机制实现用户二次确认，Redis 分布式锁（Lua 脚本原子操作）保障并发安全，禁止 LLM 直连数据库或执行写操作。

### Memory 三级上下文管理

| 层级 | 存储 | 策略 |
|------|------|------|
| **Session Memory** | LangGraph MySQL Checkpoint | 每次对话结束自动持久化 State，支持中断恢复 |
| **Summary Memory** | MySQL `conversation_summary` | Token 估算超 4000 或对话轮次超 15 轮时触发压缩，保留最近 4 条消息，其余由 LLM 压缩为不超过 300 字摘要 |
| **Long-term Memory** | MySQL `user_memory` | 对话超过 3 轮时通过 LLM 结构化提取设备偏好、服务记录、联系方式，按 user_id 严格隔离，禁止跨用户检索 |

### Guardrails 安全审查

**输入安全检查**：正则模式匹配 + LLM 语义检测双路径，覆盖五类风险：

| 风险类型 | 触发条件 | 处理 |
|----------|----------|------|
| 医疗诊断 | 用户要求诊断疾病、分析检查报告 | 路由至 Safe Reply |
| 治疗建议 | 用户要求治疗建议、手术方案 | 路由至 Safe Reply |
| 用药建议 | 用户要求推荐药品或剂量 | 路由至 Safe Reply |
| 隐私越权 | 用户试图获取他人设备或病历信息 | 路由至 Safe Reply |
| 未授权操作 | 用户请求修改他人数据、越权操作 | 路由至 Safe Reply |

**输出安全检查**：检测无依据承诺、用药建议输出、设备医疗功效宣称等模式，对绝对化断言做替换清洗并追加医疗免责声明。

### 模型路由

根据任务类型自动选择模型：

- **轻量模型**（低延迟）：Intent 分类、Safety Check、Query Rewrite、Summary、Memory Extract
- **强推理模型**（高推理能力）：RAG Answer、Troubleshooting、Rerank、Decision

模型选择记录 task_type / model_name / token_usage / latency，支持 LangSmith 追踪。

### 全链路可观测

- **LangGraph 节点追踪**：每次请求自动追踪全部节点的输入输出、延迟、异常
- **LLM 调用记录**：模型名称、任务类型、Token 消耗
- **Trace 回放**：按 trace_id 完整回放执行链路定位问题节点
- **内置告警**：Agent 失败率 / LLM 失败率 / RAG 空结果率 / P95 延迟 自动告警

---

## 项目结构

```
MedDeviceAgent/
├── app/
│   ├── agent/                  # LangGraph Agent Workflow
│   │   ├── state.py            # AgentState 全局状态定义
│   │   ├── graph.py            # Workflow 图编排 (16 节点)
│   │   ├── nodes/              # Agent 节点
│   │   │   ├── input_safety_check    # 输入安全检查
│   │   │   ├── intent_classify       # 意图识别 (AC自动机+LLM)
│   │   │   ├── context_load          # 上下文加载
│   │   │   ├── query_router          # 查询路由分发
│   │   │   ├── query_rewrite         # Query 改写优化
│   │   │   ├── rag_retrieve          # RAG 混合检索
│   │   │   ├── rag_rerank            # Rerank 重排序
│   │   │   ├── rag_answer            # RAG 答案生成
│   │   │   ├── fault_code_lookup     # 故障码精确查询
│   │   │   ├── tool_execute          # 工具调用执行
│   │   │   ├── answer_generate       # 答案合成
│   │   │   ├── output_safety_check   # 输出安全检查
│   │   │   └── memory_update         # 三级记忆更新
│   │   ├── tools/              # Tool Registry + 业务工具
│   │   │   ├── registry.py          # 工具注册中心
│   │   │   ├── create_ticket.py     # 创建维修工单
│   │   │   ├── query_warranty.py    # 保修查询
│   │   │   ├── query_device_binding.py  # 设备绑定查询
│   │   │   ├── transfer_human.py    # 转人工
│   │   │   └── create_warranty.py   # 登记保修
│   │   └── routers/
│   │       └── model_router.py      # 模型路由
│   ├── api/                    # FastAPI 路由层
│   │   ├── routers/            # RESTful API (auth/session/ticket/device/warranty/fault_code/knowledge/trace/chat)
│   │   └── middleware/         # 中间件 (metrics/rate_limit/timeout)
│   ├── models/                 # SQLAlchemy 数据模型 (16 张表) + Repository
│   ├── schemas/                # Pydantic 请求/响应 Schema
│   ├── services/               # 业务服务层
│   ├── rag/                    # RAG 检索模块
│   │   ├── retriever.py       # Qdrant 向量检索 + Metadata 过滤
│   │   ├── embedding.py       # Embedding 向量化服务
│   │   ├── chunk.py           # 文档 Chunk 切分
│   │   ├── rerank.py          # Rerank 重排序
│   │   └── bm25_index.py      # BM25 关键词索引 (SQLite FTS5 + jieba)
│   ├── memory/                 # Memory 管理
│   │   ├── checkpoint.py      # LangGraph MySQL Checkpointer
│   │   └── summary.py         # 对话摘要服务
│   ├── core/                   # 核心基础设施
│   │   ├── config.py          # Pydantic Settings 配置管理
│   │   ├── llm.py             # LLM API 客户端
│   │   ├── database.py        # MySQL 连接池
│   │   ├── qdrant.py          # Qdrant 客户端
│   │   ├── redis.py           # Redis 客户端 + Key 规范
│   │   ├── lock.py            # Redis 分布式锁 (Lua 原子操作)
│   │   ├── security.py        # JWT + bcrypt 认证
│   │   ├── prompt_manager.py  # Prompt 版本管理
│   │   ├── tracer.py          # Trace 追踪器
│   │   ├── fallback.py        # 统一降级/重试策略
│   │   ├── alert.py           # 告警规则引擎
│   │   ├── exceptions.py      # 全局异常定义 (五级错误码)
│   │   └── storage.py         # MinIO 对象存储
│   └── tasks/                  # Celery 异步任务
│       ├── embedding_tasks.py # 批量 Embedding 入库
│       ├── notification_tasks.py  # 短信/邮件通知
│       └── cleanup_tasks.py   # 数据归档清理
├── prompts/                    # Prompt 模板 (YAML 版本管理)
│   ├── intent/classify_v1.yaml
│   ├── safety/check_v1.yaml
│   ├── rag/answer_v1.yaml, rewrite_v1.yaml
│   ├── tool/ticket_draft_v1.yaml
│   ├── summary/summarize_v1.yaml
│   └── memory/extract_v1.yaml
├── alembic/                    # 数据库迁移 (16 张表)
├── tests/                      # 测试 (单元/评估/E2E)
├── frontend/                   # Vue 3 前端
└── pyproject.toml              # 项目配置
```

---

## 数据库模型

| 表名 | 用途 |
|------|------|
| `user` | 用户账号 (角色/状态) |
| `device` | 医疗设备 (SN/型号/版本/绑定用户) |
| `warranty_record` | 设备保修记录 |
| `repair_ticket` | 维修工单 (含 Human Confirm 状态机) |
| `conversation` | 对话会话 |
| `conversation_message` | 对话消息 (角色/Token) |
| `conversation_summary` | 对话摘要 (版本管理) |
| `user_memory` | 用户长期记忆 (类型/隔离) |
| `knowledge_document` | 知识库文档 (设备类型/文档类型/版本/权限) |
| `knowledge_chunk` | 文档 Chunk (向量ID/元数据) |
| `agent_trace` | Agent 链路追踪 |
| `agent_trace_node` | 节点执行记录 (输入/输出/延迟) |
| `llm_call_record` | LLM 调用记录 (模型/Token/延迟) |
| `role` | 角色定义 (RBAC) |
| `user_role` | 用户-角色关联 |
| `knowledge_permission` | 知识库文档级权限 |

---

## 快速开始

### 前置条件

确保本地已安装以下基础服务：

| 服务 | 端口 | 说明 |
|------|------|------|
| Python 3.11 | — | 后端运行环境 |
| Node.js ≥ 18 | — | 前端构建环境 |
| MySQL 8.0 | 3306 | 业务数据 + Checkpoint + Trace |
| Redis | 6379 | 缓存 / 限流 / 分布式锁 / Celery Broker |
| Qdrant | 6333 | 向量数据库 |
| LLM API Key | — | 对话与大模型交互 |

### 1. 安装依赖

```bash
# Python 依赖
pip install -e ".[dev]"

# 前端依赖
cd frontend && npm install && cd ..
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入必要配置：

```ini
# LLM
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.example.com/v1

# MySQL
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=yourpassword
MYSQL_DATABASE=med_device_agent

# Redis
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# Qdrant
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

### 3. 初始化数据库

```bash
# 先在 MySQL 中创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS med_device_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 执行迁移（16 张表）
alembic upgrade head
```

### 4. 启动基础设施

```bash
# -------------------- Redis --------------------
# Windows（下载 Redis for Windows 或 WSL）
redis-server

# macOS
brew services start redis

# Linux
sudo systemctl start redis

# -------------------- Qdrant --------------------
# 推荐 Docker 启动（无 Docker 可下载二进制运行）
docker run -d -p 6333:6333 -p 6334:6334 -v qdrant_data:/qdrant/storage qdrant/qdrant

# -------------------- MinIO（可选，文档/附件存储）--------------------
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

### 5. 启动后端

```bash
# 开发模式（热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Celery Worker（异步任务：Embedding / 通知 / 清理）
celery -A app.tasks.celery_app worker --loglevel=info -Q embedding,notification,cleanup,ticket_sync
```

启动成功后可验证：

```bash
curl http://localhost:8000/api/v1/health
# → {"status":"ok","app":"MedDeviceAgent","version":"0.1.0",...}

curl http://localhost:8000/api/docs
# → Swagger API 文档页面
```

### 6. 启动前端

```bash
cd frontend
npm run dev
```

前端默认运行在 `http://localhost:5173`，已配置代理将 `/api` 请求转发到后端 `8000` 端口。

### 7. 验证全链路

1. 浏览器打开 http://localhost:5173
2. 注册/登录账号
3. 输入设备问题（如 "监护仪报 E101 故障码是什么意思"）
4. 观察 Agent 完整链路：意图识别 → RAG 检索 → 答案生成 → 流式输出

---

## API 概览

```
POST   /api/v1/auth/login              # 登录
POST   /api/v1/session/create           # 创建会话
POST   /api/v1/chat                     # 发送消息 (SSE 流式)
WS     /api/v1/ws/support-chat/{id}     # WebSocket 实时聊天
POST   /api/v1/ticket/draft             # 创建工单草稿
POST   /api/v1/ticket/confirm           # 确认/取消工单
GET    /api/v1/ticket/{id}              # 查询工单
GET    /api/v1/warranty/{sn}            # 查询保修
GET    /api/v1/device/binding           # 设备绑定查询
GET    /api/v1/fault-code/{code}        # 故障码查询
POST   /api/v1/knowledge/upload         # 上传知识文档
GET    /api/v1/trace/{trace_id}         # Trace 回放查询
GET    /api/v1/support/queue-status     # 客服排队状态
```

所有响应统一为 `{"code": 0, "message": "success", "data": {}}` 格式。

---

## 测试

```bash
# 单元测试
pytest tests/ -v --ignore=tests/e2e --ignore=tests/eval

# RAG 评估
pytest tests/eval/rag_eval.py -v

# 意图识别评估
pytest tests/eval/intent_eval.py -v

# E2E 关键路径
pytest tests/e2e/test_critical_paths.py -v
```

---

## CI/CD

GitHub Actions:
- **Lint & Type Check**: Ruff + Mypy
- **Unit Tests**: Pytest

---

## 安全设计

- **五类风险覆盖**：医疗诊断、治疗建议、用药建议、隐私越权、未授权操作，输入输出双端检查
- **Human-in-the-loop**：高风险写操作必须用户二次确认
- **JWT 认证**：bcrypt + python-jose，支持角色权限
- **RBAC 权限**：角色 + 知识库文档级权限控制
- **分布式锁**：Redis Lua 原子操作，防并发重复提交
- **Rate Limit**：基于用户 ID + Action 的 Redis 限流
- **数据隔离**：用户私有数据不进公共知识库，Long-term Memory 按 user_id 严格隔离
