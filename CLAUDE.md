# CLAUDE.md

## 1. 项目定位

项目名称：
医疗设备智能语音客服 Agent 平台

项目目标：

基于 FastAPI + LangGraph 构建面向医疗设备售后场景的业务型 Agent 系统。

系统不是简单的 LLM Chatbot，而是通过：

- RAG 知识检索
- Tool Calling 工具执行
- Human-in-the-loop 用户确认
- Guardrails 安全控制
- Trace / Eval 可观测

实现可控、可追踪、可评估的企业级 Agent Workflow。


核心业务能力：

- 设备知识问答
- 产品说明书检索
- FAQ 查询
- 故障码解释
- 故障排查
- 保修查询
- 设备绑定查询
- 创建维修工单
- 转人工
- 医疗高风险问题拦截


---

# 2. 技术栈约束


## Backend

语言：

Python 3.11

框架：

- FastAPI
- Pydantic v2
- SQLAlchemy 2.x


## Agent

必须使用：

- LangGraph 作为 Workflow 编排框架
- LangChain 作为 LLM/RAG 工具链


Agent流程必须基于：

State -> Node -> Edge

设计。


禁止：

- 单文件大 Prompt 串联全部逻辑
- Controller 中直接调用 LLM
- Agent 节点隐藏业务逻辑


---

## RAG

技术：

- Embedding
- Qdrant（向量数据库）
- Metadata Filter
- Hybrid Retrieval（向量检索 + 关键词检索）


知识来源：

- 产品说明书
- FAQ
- 故障码
- 售后政策
- 操作文档


RAG必须支持：

- Chunk切分
- Embedding
- Metadata过滤
- TopK检索
- Rerank 重排序
- Citation追踪


Metadata至少包含：

```json
{
 "device_type":"",
 "doc_type":"",
 "version":"",
 "permission":""
}
```

禁止：

- 无过滤条件直接搜索全部知识库
- 用户私有数据进入公共知识库


---

## LLM / 模型

LLM 供应商：

DeepSeek

模型选择策略：

| 任务类型 | 推荐模型 | 说明 |
|---------|---------|------|
| Intent 分类、Summary | DeepSeek-V3（轻量） | 低延迟、低成本 |
| RAG 回答、故障排查、决策 | DeepSeek-R1（强模型） | 高推理能力 |
| Safety Check | DeepSeek-V3 + 规则 | 低延迟优先 |

---

## 语音

ASR（语音识别）：

FunASR + SenseVoice

TTS（语音合成）：

CosyVoice 2

------

# 3. Agent Workflow规范

所有Agent流程必须通过LangGraph实现。

标准Workflow：

```
User Input

 ↓

Input Safety Check

 ↓

Intent Classification

 ↓

Context Load

 ↓

Query Router

 ↓

 ┌──────────────┐
 │              │
RAG          Tool
 │              │
 ↓              ↓

Answer      Human Confirm

 ↓

Output Safety Check

 ↓

Memory Update

 ↓

Response
```

每个Node必须：

- 单一职责
- 输入明确
- 输出结构化
- 可独立Trace

Node命名要求：

```
xxx_node
```

例如：

```
intent_classify_node

rag_retrieve_node

tool_execute_node

safety_check_node
```

------

# 4. LangGraph State规范

所有流程状态必须显式定义。

State禁止：

- 隐式传递变量
- 全局变量保存上下文

推荐：

```
class AgentState(TypedDict):

    user_id: str

    session_id: str

    trace_id: str

    query: str

    intent: str

    route_type: str

    device_info: dict

    retrieved_docs: list

    tool_calls: list

    pending_action: dict

    messages: list

    summary: str

    response: str

    risk_level: str
```

State负责：

- 节点通信
- Checkpoint恢复
- Trace记录

------

# 5. Intent设计规范

意图识别采用：

规则优先 + LLM兜底

流程：

```
User Query

↓

AC自动机规则匹配

↓

命中:
    返回Intent

未命中:
    LLM结构化分类
```

高频Intent：

```
faq_query          # FAQ 查询
device_info_query  # 设备信息查询
fault_code_query   # 故障码查询
troubleshooting    # 故障排查
warranty_query     # 保修查询
device_binding     # 设备绑定查询
create_ticket      # 创建维修工单
transfer_human     # 转人工
medical_risk       # 医疗风险（安全拦截）
```

LLM分类必须返回JSON。

禁止：

直接让LLM自由输出意图。

------

# 6. Tool Calling规范

所有业务能力必须经过Tool Registry管理。

工具包括：

| Tool                   | 功能         |
| ---------------------- | ------------ |
| query_warranty         | 查询保修     |
| query_device_binding   | 查询设备绑定 |
| create_ticket          | 创建工单     |
| transfer_human         | 转人工       |

标准流程：

```
LLM

↓

Tool Intent

↓

Schema Validation

↓

Permission Check

↓

Risk Check

↓

Human Confirm

↓

Tool Execute

↓

Result
```

禁止：

LLM直接调用数据库。

禁止：

LLM直接执行写操作。

------

# 7. Human-in-the-loop规范

所有高风险操作必须人工确认。

高风险动作：

- 创建工单
- 转人工
- 修改设备信息
- 影响售后的操作

流程：

```
Agent生成操作建议

↓

保存pending_action

↓

等待用户确认

↓

执行Tool
```

State必须保存：

```
pending_action
```

------

# 8. Memory设计规范

采用三级上下文管理。

## Session Memory

存储：

当前对话上下文

使用：

LangGraph Checkpoint（MySQL 后端）

------

## Summary Memory

存储：

历史对话摘要

保存：

MySQL

------

## Long Term Memory

存储：

用户长期有效信息

要求：

必须按照：

user_id

进行隔离。

禁止：

跨用户检索历史信息。

------

# 9. Prompt管理规范

Prompt统一管理。

禁止：

代码内部硬编码Prompt。

Prompt分类：

```
prompts/

├── intent/
├── rag/
├── safety/
├── summary/
├── tool/
└── memory/
```

Prompt必须支持：

- 版本管理
- Trace记录
- AB测试

------

# 10. Model Routing规范

根据任务选择模型。

规则：

简单任务：

```
intent
classification
summary
```

使用 DeepSeek-V3（轻量模型，低延迟低成本）。

复杂任务：

```
RAG Answer
Troubleshooting
Decision
```

使用 DeepSeek-R1（强模型，高推理能力）。

模型选择必须记录：

```
model_name

task_type

token_usage

latency
```

------

# 11. Guardrails规范

医疗场景必须进行安全控制。

输入检查：

- 医疗诊断请求
- 治疗建议
- 药物建议
- 隐私请求

输出检查：

- 无依据承诺
- 错误医疗建议
- 越权回答

高风险进入：

```
safe_reply_node
```

禁止：

Agent自行给出医疗诊断。

------

# 12. Trace / Eval规范

每次请求必须生成：

```
trace_id
```

记录：

- 用户输入
- Intent结果
- Router结果
- RAG召回文档
- Metadata过滤条件
- Tool参数
- 权限检查
- Model选择
- Token消耗
- 节点耗时
- 最终输出

支持：

trace_id完整回放。

------

# 13. 数据库规范

数据库：

MySQL

ORM：

SQLAlchemy

要求：

- Model独立管理
- Schema独立管理
- Migration管理

禁止：

业务代码直接写SQL。

------

# 14. Redis规范

Redis用于：

- Session缓存
- Rate Limit
- Distributed Lock

Key格式：

```
业务:对象:ID
```

例如：

```
lock:create_ticket:user_id
```

禁止：

无过期时间缓存。

------

# 15. API规范

接口统一：

RESTful

格式：

```
/api/v1/{resource}
```

响应统一：

```
{
 "code":0,
 "message":"",
 "data":{}
}
```

Streaming接口：

使用：

SSE/WebSocket

必须支持：

- 中断
- 超时
- 异常恢复

------

# 16. 修改代码规则

任何代码修改必须：

1. 先理解现有架构
2. 不破坏已有Workflow
3. 保持Node职责单一
4. 更新对应docs
5. 增加必要测试

修改顺序：

```
需求分析

↓

设计方案

↓

修改代码

↓

测试

↓

更新文档
```

------

# 17. 禁止事项

禁止：

- 删除已有Agent节点
- 绕过LangGraph直接调用LLM
- Controller里面写业务逻辑
- Tool绕过权限检查
- 用户数据混入公共知识库
- 明文保存敏感信息
- 使用Prompt解决所有问题

------

# 18. 文档维护

以下文件必须保持同步：

```
docs/

architecture.md
requirements.md
database.md
api.md
workflow.md
```

任何架构变化必须更新对应文档。

------

# 最终目标

保持系统具备：

- 可维护
- 可扩展
- 可追踪
- 可评估
- 可回滚
- 安全可控

按照企业级 Agent 平台标准开发。