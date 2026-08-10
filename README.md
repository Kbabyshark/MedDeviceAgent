<p align="center">
  <h1 align="center">🏥 MedDeviceAgent</h1>
  <p align="center">
    <strong>医疗设备智能客服 Agent 平台 — LangGraph + RAG + HITL</strong>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python 3.11+">
    <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg" alt="FastAPI">
    <img src="https://img.shields.io/badge/LangGraph-0.6+-green.svg" alt="LangGraph">
    <img src="https://img.shields.io/badge/Vue-3.x-4FC08D.svg" alt="Vue 3">
    <img src="https://img.shields.io/badge/MySQL-8.0-orange.svg" alt="MySQL">
    <img src="https://img.shields.io/badge/Redis-7.x-DC382D.svg" alt="Redis">
  </p>
</p>

---

## 📖 目录

- [项目简介](#-项目简介)
- [技术栈](#-技术栈)
- [核心特性](#-核心特性)
- [系统架构](#-系统架构)
- [快速开始](#-快速开始)
- [环境变量](#-环境变量)
- [API 端点](#-api-端点)
- [项目结构](#-项目结构)
- [Agent Workflow](#-agent-workflow)
- [RAG 检索架构](#-rag-检索架构)
- [Guardrails 安全审查](#-guardrails-安全审查)
- [数据库模型](#-数据库模型)
- [运行测试](#-运行测试)
- [License](#-license)

---

## 📖 项目简介

**MedDeviceAgent** 是一个面向医疗设备售后场景的企业级 Agent 系统。基于 **LangGraph 16 节点 Workflow** 编排，通过 **RAG 混合检索、Tool Calling 工具执行、Human-in-the-loop 用户确认、Guardrails 安全审查、全链路 Trace 可观测** 五大能力，实现可控、可追踪、可评估的智能客服 Workflow。

核心业务覆盖：设备知识问答、产品说明书检索、FAQ 查询、故障码解释、故障排查、保修查询、设备绑定查询、创建维修工单、转人工、医疗高风险问题拦截。

---

## 🛠 技术栈

### 后端

| 类别        | 技术                                 |
| ----------- | ------------------------------------ |
| Web 框架    | FastAPI + Uvicorn                    |
| AI Workflow | LangGraph (StateGraph + Checkpoint)  |
| LLM 交互    | LangChain + LLM API 客户端           |
| 向量数据库  | Qdrant                               |
| 关键词检索  | BM25 (SQLite FTS5 + jieba)           |
| 文档解析    | MinerU API + pdfplumber              |
| 数据验证    | Pydantic v2 + Pydantic Settings      |
| ORM         | SQLAlchemy 2.x (async) + Alembic     |
| 数据库      | MySQL 8.0                            |
| 缓存 / 锁   | Redis (分布式锁、限流、Session 缓存) |
| 异步任务    | Celery (Redis Broker)                |
| 对象存储    | MinIO                                |
| 认证        | JWT (python-jose + bcrypt)           |
| 可观测      | LangSmith + structlog + 内置告警     |
| 测试        | Pytest                               |

### 前端

| 类别       | 技术                     |
| ---------- | ------------------------ |
| 框架       | Vue 3 (Composition API)  |
| 构建工具   | Vite                     |
| 语言       | TypeScript               |
| UI 组件库  | Naive UI                 |
| 状态管理   | Pinia                    |
| 路由       | Vue Router               |
| 流式通信   | SSE (Server-Sent Events) |
| 实时通信   | WebSocket                |

---

## ✨ 核心特性

### 🧠 意图识别与路由

采用 **规则优先 + LLM 兜底** 两层架构：

- **AC 自动机规则层**：预置 13 组中文关键词规则，覆盖保修查询、报修工单、转人工、故障码、设备绑定、FAQ、售后政策、医疗风险词、闲聊等 12 种意图。规则命中时按次数 + 关键词长度加权 + 写操作额外加权排序，多意图场景返回排序列表供下游路由决策
- **LLM 兜底层**：规则未命中时走 LLM 结构化分类，输出 `{intent, confidence}` JSON，降低模型调用成本和前置延迟
- **路由分发**：RAG 检索 / Tool 执行 / Fault Code 精确查询 / Safe Reply 四条路径

### 🔍 Hybrid RAG 检索

- **Qdrant 向量检索**：BGE Embedding 语义相似度匹配
- **BM25 关键词检索**：SQLite FTS5 + jieba 分词精确命中
- **RRF 融合** + **Rerank 重排序**
- **Metadata 过滤**：device_type / doc_type / permission 三级过滤，禁止无过滤条件全库搜索
- **无结果降级链**：严格过滤 → 放宽 device_type → Query Rewrite 重试 → 提示转人工

### 📄 文档解析后处理

- 集成 MinerU API 解析 PDF 输出 Markdown
- 目录块自动检测与删除、页眉页脚频率统计过滤、页码/URL/版权符号等噪声清理
- 通过 pdfplumber 提取每页锚点注入 `[Page N]` 位置标记，保证 Chunk 页码可追溯
- Chunk 切分后由 Celery 异步 Embedding 批量写入 Qdrant

### 🧩 16 节点 Agent Workflow

```
Input Safety Check → Intent Classification → Context Load → Query Router
                                                                │
                                    ┌───────────────────────────┤
                                    ↓                           ↓
                              Query Rewrite              Fault Code Lookup
                                    ↓                           ↓
                              RAG Retrieve              Tool Execute
                                    ↓                     (HITL 确认)
                              RAG Rerank                      ↓
                                    ↓                   Execute Tool
                              RAG Answer                      ↓
                                    │                           │
                                    └───────────┬───────────────┘
                                                ↓
                                        Answer Generate
                                                ↓
                                      Output Safety Check
                                                ↓
                                         Memory Update
                                                ↓
                                            Response
```

- **Human-in-the-loop**：创建工单、转人工等高风险操作通过 LangGraph `interrupt` 机制实现用户二次确认
- **Redis 分布式锁**：Lua 脚本原子操作保障并发安全，禁止 LLM 直连数据库或执行写操作
- **SSE 流式输出**：Token 级实时推送，支持中断恢复

### 🧩 三级会话记忆

| 层级     | 实现                          | 策略                                                                 |
| -------- | ----------------------------- | -------------------------------------------------------------------- |
| 工作记忆 | LangGraph MySQL Checkpoint    | 每次对话结束自动持久化 State，支持中断恢复                           |
| 短期记忆 | MySQL conversation_summary    | Token 估算超 4000 或对话轮次超 15 轮时触发压缩，保留最近 4 条消息     |
| 长期记忆 | MySQL user_memory             | 对话超过 3 轮时 LLM 结构化提取设备偏好、服务记录，按 user_id 严格隔离 |

### 🛡️ 医疗场景 Guardrails

**输入安全检查**：正则匹配 + LLM 语义检测双路径，覆盖五类风险：

| 风险类型   | 触发条件                               | 处理               |
| ---------- | -------------------------------------- | ------------------ |
| 医疗诊断   | 用户要求诊断疾病、分析检查报告         | 路由至 Safe Reply  |
| 治疗建议   | 用户要求治疗建议、手术方案             | 路由至 Safe Reply  |
| 用药建议   | 用户要求推荐药品或剂量                 | 路由至 Safe Reply  |
| 隐私越权   | 用户试图获取他人设备或病历信息         | 路由至 Safe Reply  |
| 未授权操作 | 用户请求修改他人数据、越权操作         | 路由至 Safe Reply  |

**输出安全检查**：检测无依据承诺、用药建议输出、设备医疗功效宣称等模式，对绝对化断言做替换清洗并追加医疗免责声明。

### 🔧 Tool Calling

5 个业务工具通过 Tool Registry 统一注册，执行链路：

```
LLM 生成 Tool Intent → Schema Validation → Permission Check → Risk Check → Human Confirm → Tool Execute
```

| Tool                    | 功能         | 风险等级 | 需确认 |
| ----------------------- | ------------ | -------- | ------ |
| `query_warranty`        | 查询保修状态 | 低       | 否     |
| `query_device_binding`  | 查询设备绑定 | 低       | 否     |
| `create_ticket`         | 创建维修工单 | 高       | 是     |
| `create_warranty`       | 登记设备保修 | 中       | 是     |
| `transfer_human`        | 转人工       | 高       | 是     |

### 📡 模型路由

根据任务类型自动选择模型：

- **轻量模型**（低延迟）：Intent 分类、Safety Check、Query Rewrite、Summary、Memory Extract
- **强推理模型**（高推理能力）：RAG Answer、Troubleshooting、Rerank、Decision

模型选择记录 task_type / model_name / token_usage / latency，支持 LangSmith 追踪。

### 🔎 全链路可观测

- LangGraph 节点追踪：每次请求自动追踪全部节点的输入输出、延迟、异常
- LLM 调用记录：模型名称、任务类型、Token 消耗
- Trace 回放：按 trace_id 完整回放执行链路定位问题节点
- 内置告警：Agent 失败率 / LLM 失败率 / RAG 空结果率 / P95 延迟 自动告警

---

## 🏗 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                     Vue 3 前端                                │
│     Naive UI + Pinia + Axios + SSE Stream + WebSocket        │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │
│  │ 智能问答  │  │ 工单管理  │  │ 设备管理  │  │ 管理后台   │   │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘   │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP REST + SSE + WebSocket
┌────────────────────────▼─────────────────────────────────────┐
│                      FastAPI 后端                             │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │   API Router   │  │   Services     │  │   LangGraph     │ │
│  │  · /chat       │  │  · Session     │  │  16-Node Agent  │ │
│  │  · /ticket     │  │  · Knowledge   │  │  Workflow       │ │
│  │  · /device     │  │  · Fault Code  │  │                 │ │
│  └───────┬────────┘  └───────┬────────┘  └───────┬─────────┘ │
│          │                   │                    │           │
│  ┌───────▼───────────────────▼────────────────────▼─────────┐ │
│  │                       RAG Engine                         │ │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐  │ │
│  │  │Embedding │  │  Qdrant  │  │   BM25   │  │   RRF   │  │ │
│  │  │  (BGE)   │  │  Vector  │  │ Keyword  │  │  Fusion │  │ │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Guard   │  │  Memory  │  │  MySQL   │  │   Celery     │ │
│  │ (Safety) │  │(3-Level) │  │+Redis    │  │   Worker     │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 前置要求

- **Python** `>= 3.11, < 3.12`
- **Node.js** `>= 18`
- **MySQL** 8.0
- **Redis** 7.x
- **Qdrant** (向量数据库)
- **LLM API Key**

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
LLM_API_KEY=sk-xxxxxxxx
LLM_BASE_URL=https://api.example.com/v1
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_PASSWORD=yourpassword
MYSQL_DATABASE=med_device_agent
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
```

### 3. 初始化数据库

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS med_device_agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 执行迁移（16 张表）
alembic upgrade head
```

### 4. 启动基础设施

```bash
# Redis（Windows 下载二进制 / macOS: brew services start redis / Linux: sudo systemctl start redis）
redis-server

# Qdrant
docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant

# MinIO（可选，文档/附件存储）
docker run -d -p 9000:9000 -p 9001:9001 \
  -e MINIO_ROOT_USER=minioadmin \
  -e MINIO_ROOT_PASSWORD=minioadmin \
  minio/minio server /data --console-address ":9001"
```

### 5. 启动后端

```bash
# 开发模式（热重载）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Celery Worker
celery -A app.tasks.celery_app worker --loglevel=info -Q embedding,notification,cleanup,ticket_sync
```

后端运行在 **http://127.0.0.1:8000**  
Swagger 文档：**http://127.0.0.1:8000/docs**

### 6. 启动前端

```bash
cd frontend
npm run dev
```

前端运行在 **http://localhost:5173**，已配置代理将 `/api` 请求转发到后端 `8000` 端口。

### 7. 验证全链路

1. 浏览器打开 http://localhost:5173
2. 注册/登录账号
3. 输入设备问题（如 "监护仪报 E101 故障码是什么意思"）
4. 观察 Agent 完整链路：意图识别 → RAG 检索 → 答案生成 → 流式输出

---

## ⚙️ 环境变量

完整配置项参见 [`.env.example`](.env.example)。

| 变量                       | 说明               | 默认值                            |
| -------------------------- | ------------------ | --------------------------------- |
| `LLM_API_KEY`              | 大模型 API 密钥    | **必填**                          |
| `LLM_BASE_URL`             | 大模型 API 地址    | —                                 |
| `LLM_CHAT_MODEL`           | Chat 模型名称      | —                                 |
| `LLM_REASONER_MODEL`       | Reasoning 模型名称 | —                                 |
| `EMBEDDING_MODEL`          | 向量模型名称       | `BAAI/bge-small-zh-v1.5`         |
| `MYSQL_HOST`               | MySQL 地址         | `127.0.0.1`                       |
| `MYSQL_PORT`               | MySQL 端口         | `3306`                            |
| `MYSQL_PASSWORD`           | MySQL 密码         | **必填**                          |
| `MYSQL_DATABASE`           | MySQL 数据库名     | `med_device_agent`                |
| `REDIS_HOST`               | Redis 地址         | `127.0.0.1`                       |
| `REDIS_PORT`               | Redis 端口         | `6379`                            |
| `QDRANT_HOST`              | Qdrant 地址        | `127.0.0.1`                       |
| `QDRANT_PORT`              | Qdrant 端口        | `6333`                            |
| `JWT_SECRET_KEY`           | JWT 签名密钥       | **必填**                          |
| `RATE_LIMIT_CHAT_PER_MIN`  | 聊天限流/分        | `20`                              |
| `MINIO_ENDPOINT`           | MinIO 地址         | `127.0.0.1:9000`                  |

---

## 📡 API 端点

### 认证

| 方法   | 路径                   | 说明         |
| ------ | ---------------------- | ------------ |
| `POST` | `/api/v1/auth/login`   | 用户登录     |
| `POST` | `/api/v1/auth/register`| 用户注册     |

### 问答

| 方法   | 路径                   | 说明                  |
| ------ | ---------------------- | --------------------- |
| `POST` | `/api/v1/chat`         | 知识问答（SSE 流式）  |
| `WS`   | `/api/v1/ws/support-chat/{id}` | WebSocket 实时聊天 |

### 会话

| 方法   | 路径                     | 说明         |
| ------ | ------------------------ | ------------ |
| `POST` | `/api/v1/session/create` | 创建会话     |

### 工单

| 方法   | 路径                     | 说明              |
| ------ | ------------------------ | ----------------- |
| `POST` | `/api/v1/ticket/draft`   | 创建工单草稿      |
| `POST` | `/api/v1/ticket/confirm` | 确认/取消工单     |
| `GET`  | `/api/v1/ticket/{id}`    | 查询工单详情      |

### 设备

| 方法  | 路径                       | 说明         |
| ----- | -------------------------- | ------------ |
| `GET` | `/api/v1/device/binding`   | 设备绑定查询 |

### 保修

| 方法  | 路径                       | 说明         |
| ----- | -------------------------- | ------------ |
| `GET` | `/api/v1/warranty/{sn}`    | 保修状态查询 |

### 故障码

| 方法  | 路径                         | 说明         |
| ----- | ---------------------------- | ------------ |
| `GET` | `/api/v1/fault-code/{code}`  | 故障码查询   |

### 知识库

| 方法   | 路径                       | 说明         |
| ------ | -------------------------- | ------------ |
| `POST` | `/api/v1/knowledge/upload` | 上传知识文档 |

### Trace

| 方法  | 路径                        | 说明         |
| ----- | --------------------------- | ------------ |
| `GET` | `/api/v1/trace/{trace_id}`  | Trace 回放   |

### 客服

| 方法  | 路径                            | 说明         |
| ----- | ------------------------------- | ------------ |
| `GET` | `/api/v1/support/queue-status`  | 排队状态查询 |

### 系统

| 方法  | 路径              | 说明                |
| ----- | ----------------- | ------------------- |
| `GET` | `/api/v1/health`  | 健康检查            |
| `GET` | `/api/v1/status`  | 系统状态 + 性能指标 |

所有响应统一为 `{"code": 0, "message": "success", "data": {}}` 格式。

---

## 📂 项目结构

```
MedDeviceAgent/
├── app/                         # 后端应用
│   ├── agent/                   #   LangGraph Agent Workflow
│   │   ├── state.py             #     AgentState 全局状态定义
│   │   ├── graph.py             #     Workflow 图编排 (16 节点)
│   │   ├── nodes/               #     Agent 节点
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
│   │   ├── tools/               #   Tool Registry + 业务工具
│   │   │   ├── registry.py           # 工具注册中心
│   │   │   ├── create_ticket.py      # 创建维修工单
│   │   │   ├── query_warranty.py     # 保修查询
│   │   │   ├── query_device_binding.py # 设备绑定查询
│   │   │   ├── transfer_human.py     # 转人工
│   │   │   └── create_warranty.py    # 登记保修
│   │   └── routers/
│   │       └── model_router.py       # 模型路由
│   ├── api/                     #   FastAPI 路由层
│   │   ├── routers/             #     RESTful API (14 个路由模块)
│   │   └── middleware/          #     中间件 (metrics/rate_limit/timeout)
│   ├── models/                  #   SQLAlchemy 数据模型 (16 张表)
│   ├── schemas/                 #   Pydantic 请求/响应 Schema
│   ├── services/                #   业务服务层
│   ├── rag/                     #   检索引擎
│   │   ├── retriever.py         #     Qdrant 向量检索 + Metadata 过滤
│   │   ├── embedding.py         #     Embedding 向量化服务
│   │   ├── chunk.py             #     文档 Chunk 切分
│   │   ├── rerank.py            #     Rerank 重排序
│   │   ├── bm25_index.py        #     BM25 关键词索引 (SQLite FTS5 + jieba)
│   │   └── parser.py            #     MinerU 文档解析后处理
│   ├── memory/                  #   三级记忆
│   │   ├── checkpoint.py        #     LangGraph MySQL Checkpointer
│   │   └── summary.py           #     对话摘要服务
│   ├── core/                    #   核心基础设施
│   │   ├── config.py            #     Pydantic Settings 配置管理
│   │   ├── llm.py               #     LLM API 客户端
│   │   ├── database.py          #     MySQL 连接池
│   │   ├── qdrant.py            #     Qdrant 客户端
│   │   ├── redis.py             #     Redis 客户端 + Key 规范
│   │   ├── lock.py              #     Redis 分布式锁 (Lua 原子操作)
│   │   ├── security.py          #     JWT + bcrypt 认证
│   │   ├── prompt_manager.py    #     Prompt 版本管理
│   │   ├── tracer.py            #     Trace 追踪器
│   │   ├── fallback.py          #     统一降级/重试策略
│   │   ├── alert.py             #     告警规则引擎
│   │   ├── exceptions.py        #     全局异常定义 (五级错误码)
│   │   └── storage.py           #     MinIO 对象存储
│   └── tasks/                   #   Celery 异步任务
│       ├── embedding_tasks.py   #     批量 Embedding 入库
│       ├── notification_tasks.py#     短信/邮件通知
│       └── cleanup_tasks.py     #     数据归档清理
├── prompts/                     # Prompt 模板 (YAML 版本管理)
│   ├── intent/classify_v1.yaml
│   ├── safety/check_v1.yaml
│   ├── rag/answer_v1.yaml, rewrite_v1.yaml
│   ├── tool/ticket_draft_v1.yaml
│   ├── summary/summarize_v1.yaml
│   └── memory/extract_v1.yaml
├── alembic/                     # 数据库迁移 (16 张表)
├── tests/                       # 后端测试 (pytest)
│   ├── test_intent.py, test_safety.py
│   ├── test_rag.py, test_tools.py
│   ├── test_memory.py, test_workflow.py
│   ├── test_fallback.py
│   ├── eval/ (rag_eval.py, intent_eval.py)
│   └── e2e/ (test_critical_paths.py)
├── frontend/                    # 前端应用
│   └── src/
│       ├── api/                 #   Axios 接口封装
│       ├── composables/         #   组合式函数 (useSSE / useChatWS / ...)
│       ├── components/          #   通用组件
│       ├── pages/               #   页面 (chat / admin / support)
│       ├── stores/              #   Pinia 全局状态
│       ├── types/               #   TypeScript 类型定义
│       └── router/              #   Vue Router 配置
├── docs/                        # 项目文档
└── pyproject.toml               # 项目配置
```

---

## 🔄 Agent Workflow

16 节点 Agent Workflow，每个节点职责单一，通过 **State** 通信，**Conditional Edge** 控制分支：

```
                         ┌──────────────┐
                         │   User Input  │
                         └──────┬───────┘
                                │
                         ┌──────▼───────┐
                         │ ① Input Safety│  正则 + LLM 五类风险检测
                         │    Check      │
                         └──┬───────┬───┘
                            │       │
                   (high risk)      │ (safe)
                 ┌──────────┐       │
                 │ Safe Reply│       │
                 └────┬─────┘       │
                      │      ┌──────▼───────┐
                      │      │ ② Intent      │  AC 自动机规则 + LLM 兜底
                      │      │   Classify    │  12 种意图识别
                      │      └──────┬───────┘
                      │             │
                      │      ┌──────▼───────┐
                      │      │ ③ Context Load│  设备信息 + 长期记忆 + 摘要
                      │      └──────┬───────┘
                      │             │
                      │      ┌──────▼───────┐
                      │      │ ④ Query Router│  RAG / Tool / FaultCode / SafeReply
                      │      └──┬───┬───┬──┘
                      │         │   │   │
                      │    ┌────┘   │   └──────────┐
                      │    │        │               │
                      │    │  ┌─────▼──────┐  ┌─────▼──────────┐
                      │    │  │⑤ Fault Code│  │⑨ Tool Execute  │
                      │    │  │   Lookup   │  │  (HITL 确认)    │
                      │    │  └─────┬──────┘  └─────┬──────────┘
                      │    │        │                │
                      │    │  ┌─────▼──────┐  ┌─────▼──────────┐
                      │    │  │   Answer   │  │ ⑩ Human Confirm │
                      │    │  │  Generate  │  │  (LangGraph     │
                      │    │  └─────┬──────┘  │   interrupt)    │
                      │    │        │         └─────┬──────────┘
                      │    │        │                │
                      │    │  ┌─────▼──────┐  ┌─────▼──────────┐
                      │    │  │⑥ Query     │  │⑪ Execute Tool  │
                      │    │  │  Rewrite   │  │  (确认后执行)   │
                      │    │  └─────┬──────┘  └─────┬──────────┘
                      │    │        │                │
                      │    │  ┌─────▼──────┐         │
                      │    │  │⑦ RAG       │         │
                      │    │  │  Retrieve   │         │
                      │    │  │(Vector+BM25)│         │
                      │    │  └─────┬──────┘         │
                      │    │        │                │
                      │    │  ┌─────▼──────┐         │
                      │    │  │⑧ RAG Rerank│         │
                      │    │  │  + Answer  │         │
                      │    │  └─────┬──────┘         │
                      │    │        │                │
                      └────┴────────┼────────────────┘
                                    │
                             ┌──────▼───────┐
                             │⑫ Answer       │  答案合成
                             │   Generate    │
                             └──────┬───────┘
                                    │
                             ┌──────▼───────┐
                             │⑬ Output Safety│  输出端安全审查
                             │   Check       │  + 医疗免责声明
                             └──────┬───────┘
                                    │
                             ┌──────▼───────┐
                             │⑭ Memory Update│  三级记忆写入
                             └──────┬───────┘
                                    │
                             ┌──────▼───────┐
                             │    Response   │
                             └──────────────┘
```

**关键设计**：

- 每个 Node 只做一件事，通过 `AgentState` 传递数据
- 条件边 `Query Router → fault_code_lookup / query_rewrite / tool_execute / safe_reply` 实现智能分发
- `interrupt` 实现 Human-in-the-loop，高危操作必须用户确认后才能继续
- MySQL Checkpoint 持久化 Workflow 状态，支持断点恢复

---

## 🔍 RAG 检索架构

```
文档上传
  → MinerU API (PDF 解析 → Markdown)
  → Cleaner (目录删除 / 页眉页脚过滤 / 页码注入)
  → Chunker (滑动窗口分块)
  → Embedding (BGE 向量化)
  → Celery 异步批量写入 Qdrant
  → BM25 索引追加 (SQLite FTS5 + jieba)

用户问题
  → Query Rewrite (设备型号补全 + LLM 改写)
  → Metadata Filter (device_type / doc_type / permission)
  → 并行检索:
     ├─ Qdrant.vector_search(query, top_k)  → 语义结果
     └─ BM25.keyword_search(query, top_k)   → 关键词结果
  → RRF 融合
  → Rerank 重排序
  → Top-N 返回

降级链:
  → 无结果: 放宽 device_type 过滤 → 重试
  → 仍无结果: Query Rewrite → 重试
  → 仍无结果: 提示转人工
```

---

## 🛡️ Guardrails 安全审查

### 输入安全检查

正则模式匹配 + LLM 语义检测双路径，覆盖五类风险：

| 风险类型   | 触发条件                               | 处理               |
| ---------- | -------------------------------------- | ------------------ |
| 医疗诊断   | 用户要求诊断疾病、分析检查报告         | 路由至 Safe Reply  |
| 治疗建议   | 用户要求治疗建议、手术方案             | 路由至 Safe Reply  |
| 用药建议   | 用户要求推荐药品或剂量                 | 路由至 Safe Reply  |
| 隐私越权   | 用户试图获取他人设备或病历信息         | 路由至 Safe Reply  |
| 未授权操作 | 用户请求修改他人数据、越权操作         | 路由至 Safe Reply  |

规则命中时直接路由至安全话术分支，无需调用 LLM，零延迟响应。

### 输出安全检查

检测无依据承诺、用药建议输出、设备医疗功效宣称等模式。对绝对化断言做替换清洗并追加医疗免责声明。

---

## 🗄 数据库模型

16 张表，覆盖业务数据 + Agent 链路追踪 + 权限管理：

| 表名                    | 用途                                |
| ----------------------- | ----------------------------------- |
| `user`                  | 用户账号 (角色/状态)                |
| `device`                | 医疗设备 (SN/型号/版本/绑定用户)    |
| `warranty_record`       | 设备保修记录                        |
| `repair_ticket`         | 维修工单 (含 HITL 状态机)           |
| `conversation`          | 对话会话                            |
| `conversation_message`  | 对话消息 (角色/Token)               |
| `conversation_summary`  | 对话摘要 (版本管理)                 |
| `user_memory`           | 用户长期记忆 (按 user_id 严格隔离)  |
| `knowledge_document`    | 知识库文档 (设备类型/文档类型/权限) |
| `knowledge_chunk`       | 文档 Chunk (向量ID/元数据)          |
| `agent_trace`           | Agent 链路追踪                      |
| `agent_trace_node`      | 节点执行记录 (输入/输出/延迟)       |
| `llm_call_record`       | LLM 调用记录 (模型/Token/延迟)      |
| `role`                  | 角色定义 (RBAC)                     |
| `user_role`             | 用户-角色关联                       |
| `knowledge_permission`  | 知识库文档级权限                    |

---

## 🧪 运行测试

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

## 📄 License

本项目基于 **MIT License** 开源。

---

<p align="center">
  <sub>Built with ❤️ using FastAPI + LangGraph + Vue 3</sub>
</p>
