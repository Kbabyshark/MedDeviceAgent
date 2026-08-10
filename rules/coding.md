# Coding Rules

## 1. 基础开发原则


本项目为医疗设备智能客服 Agent 平台。


开发必须遵循：

- 高内聚
- 低耦合
- 模块职责单一
- Workflow可追踪
- Tool调用安全
- 数据访问隔离
- 所有关键流程可观测


禁止：

- 单文件堆积业务逻辑
- API直接调用LLM
- Node中直接操作数据库
- Tool绕过权限校验
- 修改核心架构未同步文档



---

# 2. 技术规范


## Backend


固定：



Python 3.11

FastAPI

Pydantic v2

SQLAlchemy 2.x

LangGraph

LangChain

Redis

MySQL

Qdrant（向量数据库）

DeepSeek（LLM）

FunASR + SenseVoice（ASR）

CosyVoice 2（TTS）

---

# 3. 项目目录规范


推荐结构：

app/

├── api/
 │   └── routers/

├── core/
 │   ├── config.py
 │   ├── security.py
 │   └── logger.py

├── agent/

│   ├── graph.py
 │   ├── state.py
 │   ├── nodes/
 │   ├── routers/
 │   └── tools/

├── rag/

│   ├── retriever.py
 │   ├── embedding.py
 │   ├── chunk.py
 │   └── rerank.py

├── memory/

│   ├── checkpoint.py
 │   └── summary.py

├── services/

├── models/

├── schemas/

└── utils/

---

# 4. Python代码规范


## 4.1 命名规范


变量：

```python
user_id
trace_id
session_id
```

函数：

```
get_user_memory()

execute_tool()

retrieve_documents()
```

类：

```
AgentState

ToolExecutor

RagRetriever
```

禁止：

```
a

tmp

data1
```

------

# 5. FastAPI规范

## Router职责

Router只负责：

- 参数接收
- 参数校验
- 调用Service
- 返回Response

禁止：

```
@router.post("/chat")
async def chat():

    call_llm()

    search_vector()

    save_mysql()
```

正确：

```
@router.post("/chat")
async def chat(req):

    return await chat_service.run(req)
```

------

# 6. Service层规范

Service负责：

- 业务流程
- 数据组合
- 调用Agent

例如：

```
ChatService

    |
    |
    AgentWorkflow
```

禁止：

Service直接拼Prompt。

------

# 7. LangGraph规范

## 7.1 State统一管理

所有节点必须通过State通信。

示例：

```
class AgentState(TypedDict):

    user_id:str

    session_id:str

    query:str

    intent:str

    documents:list

    response:str
```

禁止：

节点之间：

```
global variable
```

------

# 7.2 Node规范

每个Node：

只负责一个职责。

例如：

正确：

```
intent_node

rag_node

tool_node

memory_node
```

错误：

```
agent_node():

    classify()

    search()

    call_tool()

    generate_answer()
```

------

# 7.3 Node命名规范

统一：

```
xxx_node
```

例如：

```
safety_check_node

intent_classify_node

rag_retrieve_node

tool_execute_node
```

------

# 8. Agent Workflow规范

Workflow必须：

- 支持分支
- 支持重试
- 支持Trace
- 支持状态恢复

新增Node必须同步：

```
docs/workflow.md
```

------

# 9. RAG开发规范

## Retriever职责

Retriever只负责：

- Query处理
- Embedding
- Vector Search
- Metadata Filter

禁止：

Retriever生成答案。

------

## Metadata必须过滤

所有企业知识检索必须携带：

```
{
"device_type":"",
"doc_type":"",
"version":"",
"permission":""
}
```

禁止：

无条件：

```
vector.search(query)
```

------

# 10. Prompt规范

所有Prompt统一管理。

目录：

```
prompts/


├── intent/

├── rag/

├── safety/

├── summary/

└── tool/
```

禁止：

代码中：

```
prompt="你是客服助手..."
```

必须：

```
prompt_manager.get("rag_answer")
```

------

# 11. Model Routing规范

模型选择必须经过：

```
ModelRouter
```

根据：

- task_type
- risk_level
- token长度
- 成本

决定模型。

禁止：

业务代码直接指定模型。

错误：

```
llm=qwen_max
```

正确：

```
model_router.select(task)  # 返回 DeepSeek-V3 或 DeepSeek-R1
```

------

# 12. Tool开发规范

## Tool结构

每个Tool必须包含：

```
class Tool:

    name           # query_warranty / query_device_binding / create_ticket / transfer_human

    description

    input_schema

    execute()
```

------

## Tool执行流程

固定：

```
LLM

↓

Tool Registry

↓

Schema Validate

↓

Permission Check

↓

Risk Check

↓

Human Confirm

↓

Execute
```

禁止：

LLM直接调用业务接口。

------

# 13. Human-in-the-loop规范

高风险操作：

必须：

```
pending_action
```

例如：

```
{
"type":"create_ticket",
"status":"waiting_confirm"
}
```

用户确认前：

禁止执行。

------

# 14. Database规范

## ORM规范

使用：

SQLAlchemy ORM

禁止：

业务代码散落SQL。

------

## 数据访问层

统一：

```
Repository
```

例如：

```
UserRepository

TicketRepository

TraceRepository
```

------

# 15. Redis规范

Redis用途：

允许：

- Session缓存
- Rate Limit
- Distributed Lock
- 临时状态

Key规范：

```
业务:类型:id
```

例如：

```
rate_limit:chat:user001


lock:create_ticket:SN001
```

------

# 16. Trace规范

所有Agent节点必须记录Trace。

必须包含：

```
{
"trace_id":"",
"node":"",
"input":"",
"output":"",
"latency":"",
"error":""
}
```

禁止：

关键流程无日志。

------

# 17. 异常处理规范

禁止：

```
except Exception:

    pass
```

必须：

```
try:

except Exception as e:

    logger.error()

    raise BusinessException()
```

------

# 18. 日志规范

日志必须包含：

```
trace_id

session_id

user_id

node_name
```

示例：

```
logger.info(
"rag retrieve success",
extra={
"trace_id":trace_id
}
)
```

------

# 19. 测试规范

必须覆盖：

## Agent测试

包括：

- 意图识别
- RAG召回
- Tool调用
- Workflow分支

------

## API测试

使用：

```
pytest
```

------

# 20. AI Coding约束

AI修改代码时必须：

1. 先理解现有Workflow
2. 不破坏State结构
3. 不新增重复功能
4. 不修改公共接口
5. 修改后同步docs

------

# 21. 禁止事项

禁止：

- 删除Trace字段
- 删除Safety Check
- 绕过Human确认
- 直接调用LLM
- 直接操作Vector DB
- 在Node中写业务SQL
- 修改Agent架构不更新workflow.md

------

# 22. 开发优先级

开发顺序：

```
需求

↓

Workflow设计

↓

State设计

↓

Node实现

↓

Service封装

↓

API暴露

↓

测试

↓

文档更新
```

------

# 总结

本项目代码必须保证：

```
可维护

可扩展

可追踪

可回滚

可评估

安全可控
```

所有Agent能力必须通过Workflow编排完成，而不是通过单Prompt堆叠实现。