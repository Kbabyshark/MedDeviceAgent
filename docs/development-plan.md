# 开发计划

## 概述

本文档定义医疗设备智能语音客服 Agent 平台的完整开发路线图。

**开发起点**：文档完善 + 代码骨架完成（78 个文件），所有业务逻辑标记为 `# TODO`，外部服务均未对接。

**开发终点**：生产可用，通过全部验收标准。

**总轮数**：9 轮，每轮迭代周期约 1-2 周。

**开发约束**：开发过程仅编写代码，不连接真实外部服务、不执行 API 调用、不运行测试。所有外部服务调用（DeepSeek API、数据库操作等）仅封装到代码层面，由开发者自行启动服务后验证。

---

## 全景路线图

```
Phase 1         Phase 2         Phase 3         Phase 4         Phase 5
基础设施 ────→ Agent 核心 ────→ 安全+确认 ────→ 多轮记忆 ────→ 流式+语音
  │                │                │                │                │
  │ MySQL          │ Intent         │ Safety Check   │ Checkpoint     │ SSE Stream
  │ Redis          │ Router         │ Human Confirm  │ Summary        │ WebSocket
  │ Qdrant         │ RAG Pipeline   │ Safe Reply     │ Long-term Mem  │ ASR/TTS
  │ DeepSeek       │ Tool Execute   │                │                │
  └────────────────┴────────────────┴────────────────┴────────────────┘
                                       │
Phase 6         Phase 7         Phase 8         Phase 9
知识库管理 ────→ 可观测+评估 ────→ 生产加固 ────→ 测试+部署
  │                │                │                │
  │ 文档上传       │ Trace 记录     │ Rate Limit     │ Unit Test
  │ Chunk/Embed    │ Eval 指标      │ 分布式锁       │ CI/CD
  │ 版本管理       │ 成本分析       │ 异步任务       │ 部署文档
  └────────────────┴────────────────┴────────────────┘
```

---

# Phase 1: 基础设施打通

## 目标

所有外部服务（MySQL、Redis、Qdrant、DeepSeek API）完成连接和验证，`uv run uvicorn app.main:app` 无报错启动。

## 当前状态

- [pyproject.toml](pyproject.toml) 已声明所有依赖
- [config.py](app/core/config.py) Pydantic Settings 已定义全部配置项
- 各模块代码仅含骨架和 `# TODO`

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 1.1 | SQLAlchemy 异步引擎 + Session Factory | `app/core/database.py`（新建） | `async_session_factory`，连接池配置 |
| 1.2 | Alembic 初始化 + Migration 文件生成 | `alembic/` 目录 | 16 张表 Migration 脚本（不执行，仅生成） |
| 1.3 | Redis 客户端封装 | `app/core/redis.py`（新建） | `RedisClient` 封装，含连接池和 Key 规范 |
| 1.4 | Qdrant 客户端封装 + Collection 定义 | `app/core/qdrant.py`（新建） | `QdrantClient` 封装，Collection 创建逻辑 |
| 1.5 | DeepSeek API 客户端封装（仅封装，不连接） | `app/core/llm.py`（新建） | 统一 LLM 调用接口，Mock 模式支持离线开发 |
| 1.6 | Embedding API 客户端封装（仅封装） | `app/rag/embedding.py`（补充） | `embed()` / `embed_batch()` 接口 |
| 1.7 | 启动时配置校验 | `app/main.py`（补充 lifespan） | 启动时校验配置完整性，缺失必填项即时报错 |
| 1.8 | `uv run uvicorn app.main:app` 可启动 | — | `GET /api/health` 返回 `{"status":"ok"}`（不依赖外部服务） |

## 验收条件

```
✅ docker compose up -d 启动全部 6 个服务成功
✅ GET /api/health 返回 ok（无需外部服务）
✅ MySQL 16 张表 Migration 脚本生成正确
✅ Redis 客户端封装完成，Key 格式符合规范
✅ Qdrant 客户端封装完成，Collection Schema 定义完整
✅ DeepSeek LLM 客户端封装完成，Mock 模式可切换
✅ 日志格式为结构化 JSON
```

---

# Phase 2: Agent 核心链路

## 目标

单轮 Agent 对话端到端代码闭环：用户输入 → Agent Workflow → 各节点逻辑完整（LLM 调用封装完成，Mock 模式可验证流程）。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 2.1 | Prompt Manager 实现（加载 YAML，版本选择） | `app/core/prompt_manager.py`（新建） | `prompt_manager.get("rag_answer", "v1")` 返回 Prompt 模板 |
| 2.2 | Intent Classify LLM fallback（封装调用，不实际连接） | `intent_classify.py` | AC 自动机优先 + LLM 结构化分类兜底代码 |
| 2.3 | Query Rewrite LLM 调用封装 | `query_rewrite.py` | 短 Query → 完整检索 Query 改写逻辑 |
| 2.4 | RAG Retrieve Qdrant 调用封装 | `rag_retrieve.py` + `rag/retriever.py` | 向量检索 + Metadata 过滤代码 |
| 2.5 | RAG Rerank 代码实现 | `rag_rerank.py` + `rag/rerank.py` | Top-20 → Rerank → Top-5 逻辑 |
| 2.6 | RAG Answer LLM 调用封装 | `rag_answer.py` | Prompt 拼接 + LLM 调用 + Citation 提取代码 |
| 2.7 | Tool Execute（只读）Repository 层实现 | `tool_execute.py` + `query_warranty.py` + `query_device_binding.py` | 查询类 Tool 的 MySQL 查询代码 |
| 2.8 | Answer Generate 结果整合 | `answer_generate.py` | RAG + Tool 结果合并输出逻辑 |
| 2.9 | ChatService 调用完整 Workflow | `chat_service.py` + `graph.py` | `graph.ainvoke(state)` 全链路节点连通 |
| 2.10 | `POST /api/v1/chat` 接口完整 | `routers/chat.py` | API → Service → Graph → Response 链路 |

## 验收条件

```
✅ Prompt Manager 正确加载 YAML 模板，支持版本选择
✅ AC 自动机命中 → 直接返回 Intent；未命中 → 正确调用 LLM 分类函数（Mock 模式下返回预期结果）
✅ Query Rewrite 逻辑正确拼接设备信息到检索 Query
✅ RAG Retrieve 正确构建 Qdrant Filter 条件
✅ RAG Answer Prompt 正确拼接 Context + Query + Citations
✅ Model Router 按 task_type 正确选择 DeepSeek-V3 / R1
✅ Tool 查询类（warranty / device_binding）Repository 查询逻辑完整
✅ ChatService 串联全部 Node，State 在各节点间正确传递
```

---

# Phase 3: 安全与确认

## 目标

所有安全检测和 Human-in-the-loop 流程完整可用。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 3.1 | Input Safety Check 对接 LLM | `safety_check.py` | 医疗诊断/用药请求 → risk_level=high |
| 3.2 | Output Safety Check 对接 LLM | `safety_check.py` | 无依据承诺/错误医疗建议 → 改写输出 |
| 3.3 | Medical Risk → Safe Reply 链路 | `graph.py` | high risk → `_safe_reply_wrapper` → 标准安全回复 |
| 3.4 | Human-in-the-loop 中断机制 | `graph.py` + `tool_execute.py` | `interrupt_before` + `pending_action` 写入 State |
| 3.5 | 用户确认/取消流程 | `routers/ticket.py` → `ticket/confirm` | 确认 → execute；取消 → cancel |
| 3.6 | 确认超时处理 | `tool_execute.py` | 30 分钟超时 → `pending_action` 自动取消 |
| 3.7 | Rate Limit 限流中间件 | `app/api/middleware/rate_limit.py`（新建） | Redis `rate_limit:{action}:{user_id}` |

## 验收条件

```
✅ "我应该吃什么药" → safe_reply，不触发后续节点
✅ "帮我创建工单" → 生成 pending_action，等待确认
✅ POST /api/v1/ticket/confirm {confirm:true} → 工单创建成功
✅ POST /api/v1/ticket/confirm {confirm:false} → 工单取消
✅ 高频请求 → 429 Too Many Requests
```

---

# Phase 4: 多轮对话与记忆

## 目标

上下文感知的多轮对话，用户可连续提问 10+ 轮不丢失上下文。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 4.1 | LangGraph AsyncMySQLSaver 配置 | `graph.py` + `checkpoint.py` | Checkpoint 持久化到 MySQL |
| 4.2 | Context Load 实现 | `context_load.py` | 从 Checkpoint 恢复 session state |
| 4.3 | Summary Memory 触发 + LLM 摘要 | `summary.py` + Prompt `summary/summarize_v1.yaml` | Token > 4000 或轮数 > 15 自动压缩 |
| 4.4 | Long-term Memory 提取与存储 | `memory_update.py` + `user_memory` 表 | 提取设备偏好、服务记录等持久信息 |
| 4.5 | user_id 隔离验证 | 全部 Memory 模块 | 跨用户查询返回空 |
| 4.6 | 历史消息分页查询 | `routers/session.py` | `GET /session/{id}/messages?page=1` |

## 验收条件

```
✅ 连续 5 轮对话，第 6 轮能引用第 1 轮的内容
✅ 对话超 15 轮后，Summary 自动触发，Prompt 长度不超 4K
✅ 用户 A 的设备信息不会被用户 B 检索到
✅ 会话关闭后重开，Checkpoint 恢复上一轮状态
✅ GET /session/{id}/messages 分页返回历史
```

---

# Phase 5: 流式与语音

## 目标

SSE 流式输出 + WebSocket 语音双向通信完成。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 5.1 | SSE 流式 Workflow 执行 | `chat_service.py` → `graph.astream()` | 9 种事件类型全部触发 |
| 5.2 | Token 级流式输出 | `rag_answer.py` → LLM stream | 前端逐字展示 |
| 5.3 | WebSocket 语音网关 | `app/api/routers/voice_ws.py`（新建） | `ws://host/api/v1/ws/chat/{session_id}` |
| 5.4 | FunASR + SenseVoice 集成 | `app/voice/asr.py`（新建） | 语音 Base64 → 文本，< 500ms |
| 5.5 | CosyVoice 2 集成 | `app/voice/tts.py`（新建） | 文本 → 语音 Base64，流式合成 |
| 5.6 | WebSocket 心跳 + 断线重连 | `voice_ws.py` | 30s ping/pong，断线恢复 session |
| 5.7 | 端到端语音链路代码闭环 | — | 语音输入 → ASR → Agent → TTS → 语音输出代码链路 |

## 验收条件

```
✅ POST /api/v1/chat/stream → SSE 9 种事件类型全部触发
✅ SSE 9 种事件类型代码完整
✅ WebSocket 连接认证代码正确（Token 解析 + 心跳协议）
✅ ASR 客户端封装完成（语音 Base64 → 文本接口）
✅ TTS 客户端封装完成（文本 → 语音 Base64 接口）
✅ 语音全链路代码串联：ASR → Agent State → TTS
✅ 30s 心跳超时逻辑正确，断线重连 session 恢复逻辑正确
```

---

# Phase 6: 知识库管理

## 目标

管理员可通过 API 上传文档，自动完成 Chunk → Embedding → Qdrant 入库。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 6.1 | 文档上传 API | `routers/knowledge.py`（新建） | `POST /api/v1/admin/knowledge/upload` |
| 6.2 | PDF/Word/Markdown 解析 | `app/rag/parser.py`（新建） | 统一提取纯文本 |
| 6.3 | Chunk 切分 + Metadata 继承 | `chunk.py` + Celery | 512 token/chunk，overlap 64 |
| 6.4 | 批量 Embedding + Qdrant Upsert | `embedding_tasks.py` + `retriever.py` | Celery 异步处理，支持大文档 |
| 6.5 | 文档版本更新流程 | `routers/knowledge.py` | 旧版本标记 deprecated → 新 Chunk 入库 → 替换向量 |
| 6.6 | 知识检索测试 API | `routers/knowledge.py` | `POST /api/v1/knowledge/search` 返回检索结果 + score |
| 6.7 | 管理员权限校验 | `deps.py` + RBAC | 仅 admin 角色可上传/删除文档 |
| 6.8 | 知识库文档状态查看 | `routers/knowledge.py` | `GET /api/v1/admin/knowledge/{doc_id}/status` |

## 验收条件

```
✅ 上传产品说明书 PDF → Chunk 切分正确 → Qdrant 可检索
✅ 同文档新版本上传 → 旧 Chunk 过期 → 新 Chunk 生效
✅ POST /api/v1/knowledge/search → 返回检索结果 + metadata
✅ 普通用户调用 upload → 403 Forbidden
✅ 大文档（100 页）→ Celery 异步处理 → 不阻塞 API
```

---

# Phase 7: 可观测与评估

## 目标

完整 Trace 记录 + RAG/Intent/Tool 评估体系建立。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 7.1 | Trace 自动记录到 MySQL | 各 Node → `agent_trace` + `agent_trace_node` | 每次请求自动写入 Trace 表 |
| 7.2 | LLM 调用记录（token + latency） | `llm_call_record` 表 | 每次 LLM 调用自动记录 |
| 7.3 | Trace 查询 API | `routers/trace.py`（新建） | `GET /api/v1/trace/{trace_id}` 返回完整链路 |
| 7.4 | Trace 回放功能 | `routers/trace.py` | 按 trace_id 重放完整 Workflow |
| 7.5 | RAG 评估数据集构建 | `tests/eval/rag_eval.py`（新建） | 50+ 标注 QA 对 |
| 7.6 | RAG 评估指标（Recall / Precision / MRR） | `tests/eval/rag_eval.py` | 自动评估脚本 |
| 7.7 | Intent 分类准确率评估 | `tests/eval/intent_eval.py`（新建） | AC 规则命中率 + LLM 分类准确率 |
| 7.8 | 成本分析仪表板 | `routers/admin.py`（新建） | 按天/按任务类型统计 Token 消耗和费用 |

## 验收条件

```
✅ 每次请求完成后，agent_trace 表新增 1 条 + 对应 N 条 node 记录
✅ GET /api/v1/trace/{trace_id} → 返回完整节点链路
✅ RAG Recall@5 > 85%
✅ Intent 分类综合准确率 > 90%
✅ 仪表板显示本月 Token 总消耗和费用
```

---

# Phase 8: 生产加固

## 目标

系统达到 100 并发、P95 < 5s 的生产性能标准。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 8.1 | Redis 分布式锁（create_ticket, transfer_human） | `tool_execute.py` + `app/core/lock.py`（新建） | `lock:create_ticket:{user_id}:{device_sn}` |
| 8.2 | 全局异常处理完善 | `main.py` + 各 Node | 任何异常不导致 Workflow 中断 |
| 8.3 | LLM 调用重试 + Fallback | `llm.py` | 失败 → 重试 2 次 → V3 兜底 |
| 8.4 | RAG 检索失败 Fallback | `rag_retrieve.py` | 无结果 → Query Rewrite 重试 → 提示转人工 |
| 8.5 | Celery 通知任务（短信/邮件） | `notification_tasks.py`（新建） | 工单创建成功 → 通知用户 |
| 8.6 | 数据归档定时任务 | `cleanup_tasks.py` | Trace 90 天 → 归档；Session 365 天 → 归档 |
| 8.7 | 限流策略调优 | `rate_limit.py` | 按接口、用户、IP 三维限流 |
| 8.8 | 性能压测 + Profile | Locust / py-spy | P95 < 5s @ 100 并发 |
| 8.9 | 日志 + 告警规则 | `logger.py` + Prometheus | Agent 失败率 > 5% → 告警 |

## 验收条件

```
✅ Redis 分布式锁代码完整，lock/unlock 逻辑正确
✅ LLM 调用重试 + Fallback 代码逻辑正确
✅ RAG 无结果 Fallback 流程完整
✅ Trace 数据归档 Celery 定时任务代码完整
✅ 限流中间件代码完整（三维限流：接口/用户/IP）
```

---

# Phase 9: 测试与部署

## 目标

测试覆盖率 ≥ 80%，CI/CD 就绪，生产部署文档完整。

## 任务清单

| # | 任务 | 涉及文件 | 预期产出 |
|---|------|---------|---------|
| 9.1 | 单元测试全覆盖 | `tests/` | 覆盖率 ≥ 80% |
| 9.2 | 集成测试（数据库、Qdrant、Redis） | `tests/integration/`（新建） | 外服务真实调用测试 |
| 9.3 | E2E 测试（关键业务路径 5 条） | `tests/e2e/`（新建） | FAQ / 保修 / 工单 / 转人工 / 安全拦截 |
| 9.4 | CI/CD Pipeline（GitHub Actions） | `.github/workflows/ci.yml`（新建） | Lint → Test → Build Docker → Push |
| 9.5 | 生产环境 docker-compose | `docker-compose.prod.yml`（新建） | 非 root 用户、资源限制、secrets 管理 |
| 9.6 | 部署文档 | `docs/deployment.md`（新建） | 逐步部署指南 + 环境 Checklist |
| 9.7 | API 文档自动生成 | FastAPI 自带 + Redoc | `/api/docs` 在线可交互文档 |
| 9.8 | 最终文档同步 | `docs/*.md` + `CLAUDE.md` | 全部文档与代码一致 |

## 验收条件

```
✅ 单元测试代码覆盖全部 Node + Tool + Service
✅ 集成测试代码覆盖数据库 / Qdrant / Redis 操作
✅ E2E 测试代码覆盖 5 条关键业务路径
✅ CI 配置文件完整：ruff + mypy + pytest + docker build
✅ docker-compose.prod.yml 生产部署编排文件就绪
✅ /api/docs 在线文档无报错
✅ docs/*.md 全部文档与代码一致
```

---

# 里程碑总览

| Phase | 名称 | 核心交付 | 验收信号 |
|-------|------|---------|---------|
| **P1** | 基础设施打通 | MySQL / Redis / Qdrant / DeepSeek 客户端封装 | `GET /api/health` → ok（无外部依赖） |
| **P2** | Agent 核心链路 | 11 个节点 + Prompt Manager + Repository 完成 | Agent Workflow 全链路代码闭环 |
| **P3** | 安全与确认 | Guardrails + Human Confirm 代码完整 | 高风险拦截 + 工单确认流程 |
| **P4** | 多轮对话与记忆 | Checkpoint + Summary + Long-term Memory 代码完整 | 多轮上下文管理逻辑正确 |
| **P5** | 流式与语音 | SSE + WebSocket + ASR/TTS 封装完成 | 语音全链路代码闭环 |
| **P6** | 知识库管理 | 文档上传 → Chunk → Embedding 入库代码完整 | 知识库管理 CRUD |
| **P7** | 可观测与评估 | Trace 记录 + Eval 评估脚本就绪 | trace_id 回放代码 + 评估数据集 |
| **P8** | 生产加固 | 限流/锁/重试/归档代码完整 | 异常处理 + Fallback + 定时任务 |
| **P9** | 测试与部署 | 测试代码 + CI 配置 + 部署文档 | 一键部署到生产 |

---

# 并行策略

以下 Phase 可部分并行推进：

```
P1 (基础设施) ──┬── P2 (Agent 核心) ── P3 (安全确认) ── P4 (多轮记忆)
                │
                ├── P6 (知识库管理) ── 可与 P3/P4 并行
                │
                └── P5 (流式语音) ──── 可与 P3/P4 并行

P7 (可观测) ──── 建议在 P3 完成后启动

P8 (生产加固) ── 建议在 P4 完成后启动

P9 (测试部署) ── 贯穿全程，最后一轮集中收尾
```

> **建议**：P1 + P2 串行完成（打好地基），P3/P4/P5/P6 可分配不同开发者并行推进，P7 贯穿迭代，P8/P9 收尾。
