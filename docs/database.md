# 数据模型设计文档

## 1. 文档概述


本文档描述医疗设备智能语音客服 Agent 平台的数据存储设计。


系统采用多存储架构：

- MySQL
- Redis
- Vector Database


分别承担：

| 存储      | 职责                                      |
| --------- | ----------------------------------------- |
| MySQL     | 业务数据、会话数据、Trace数据、Memory数据 |
| Redis     | 缓存、限流、分布式锁、临时状态            |
| Vector DB | 知识库Embedding、用户Summary向量          |



整体设计目标：

- 数据隔离
- 状态可恢复
- 支持Agent多轮任务
- 支持Trace回放
- 支持知识检索



---

# 2. 数据架构


```text

                 Agent Request

                       |

              LangGraph State

                       |

        ----------------------------

        |             |            |

     MySQL        Redis       Vector DB

        |             |            |

业务数据       临时状态       语义检索数据

会话记录       锁/缓存        文档Embedding

Trace          限流          Summary Embedding
```

------

# 3. MySQL数据设计

MySQL主要保存长期结构化数据。

包括：

- 用户数据
- 设备数据
- 工单数据
- 会话数据
- Memory数据
- Trace数据

------

# 4. 用户相关表

## 4.1 user 用户表

用途：

保存客服系统用户基础信息。

表：

```
user
```

字段：

| 字段          | 类型     | 说明      | 索引 |
| ------------- | -------- | --------- | ---- |
| id            | bigint   | 用户ID    | PK   |
| username      | varchar  | 用户名    |      |
| phone         | varchar  | 手机号    | UK   |
| email         | varchar  | 邮箱      | UK   |
| password_hash | varchar  | 密码哈希  |      |
| role          | varchar  | 角色      | IDX  |
| status        | tinyint  | 状态      |      |
| created_at    | datetime | 创建时间  |      |
| updated_at    | datetime | 更新时间  |      |

role 枚举：

```
admin           # 管理员
customer_agent  # 客服人员
user            # 普通用户
```

索引设计：

- PK: `id`
- UK: `phone`, `email`
- IDX: `role`, `status`

说明：

所有用户相关数据必须通过：

```
user_id
```

进行隔离。

------

# 5. 设备相关表

## 5.1 device 设备表

用途：

保存医疗设备信息。

字段：

| 字段        | 类型     | 说明       | 索引 |
| ----------- | -------- | ---------- | ---- |
| id          | bigint   | 设备ID     | PK   |
| device_sn   | varchar  | 设备序列号 | UK   |
| device_type | varchar  | 设备型号   | IDX  |
| version     | varchar  | 软件版本   |      |
| user_id     | bigint   | 所属用户   | IDX  |
| status      | varchar  | 设备状态   |      |
| created_at  | datetime | 创建时间   |      |
| updated_at  | datetime | 更新时间   |      |

索引设计：

- PK: `id`
- UK: `device_sn`
- IDX: `device_type`, `user_id`, `(user_id, device_type)`

用于：

- 设备绑定查询
- 故障分析
- 保修查询

------

# 6. 保修业务表

## 6.1 warranty_record

用途：

保存设备保修信息。

字段：

| 字段       | 类型     | 说明     | 索引 |
| ---------- | -------- | -------- | ---- |
| id         | bigint   | ID       | PK   |
| device_sn  | varchar  | 设备SN   | IDX  |
| user_id    | bigint   | 所属用户 | IDX  |
| start_date | date     | 开始时间 |      |
| end_date   | date     | 结束时间 |      |
| status     | varchar  | 状态     |      |
| created_at | datetime | 创建时间 |      |
| updated_at | datetime | 更新时间 |      |

索引设计：

- PK: `id`
- IDX: `device_sn`, `user_id`, `(device_sn, status)`

Tool：

```
query_warranty
```

通过该表查询。

------

# 7. 工单数据设计

## 7.1 repair_ticket

用途：

保存维修工单。

字段：

| 字段           | 类型     | 说明       | 索引 |
| -------------- | -------- | ---------- | ---- |
| id             | bigint   | 工单ID     | PK   |
| user_id        | bigint   | 用户       | IDX  |
| device_sn      | varchar  | 设备       | IDX  |
| fault_desc     | text     | 故障描述   |      |
| fault_category | varchar  | 故障分类   | IDX  |
| priority       | varchar  | 优先级     |      |
| contact_name   | varchar  | 联系人     |      |
| contact_phone  | varchar  | 联系电话   |      |
| assigned_to    | bigint   | 分配客服   | IDX  |
| status         | varchar  | 状态       | IDX  |
| created_by     | varchar  | 创建来源   |      |
| created_at     | datetime | 创建时间   |      |
| updated_at     | datetime | 更新时间   |      |

priority 枚举：

```
low        # 低
medium     # 中
high       # 高
urgent     # 紧急
```

索引设计：

- PK: `id`
- IDX: `user_id`, `device_sn`, `fault_category`, `assigned_to`, `status`, `(user_id, status)`, `(status, created_at)`

状态：

```
draft

pending_confirm

created

processing

completed

cancelled
```

------

# 8. Agent会话数据

## 8.1 conversation

用途：

保存用户会话。

字段：

| 字段       | 类型     | 说明          | 索引 |
| ---------- | -------- | ------------- | ---- |
| id         | bigint   | 会话ID        | PK   |
| user_id    | bigint   | 用户          | IDX  |
| session_id | varchar  | Agent Session | UK   |
| title      | varchar  | 标题          |      |
| status     | varchar  | 状态          |      |
| created_at | datetime | 创建时间      |      |
| updated_at | datetime | 更新时间      |      |

索引设计：

- PK: `id`
- UK: `session_id`
- IDX: `user_id`, `status`

------

## 8.2 conversation_message

用途：

保存消息记录。

字段：

| 字段        | 类型     | 说明      | 索引 |
| ----------- | -------- | --------- | ---- |
| id          | bigint   | 消息ID    | PK   |
| session_id  | varchar  | 会话      | IDX  |
| role        | varchar  | 角色      |      |
| content     | text     | 内容      |      |
| token_usage | int      | Token数量 |      |
| created_at  | datetime | 时间      |      |

索引设计：

- PK: `id`
- IDX: `session_id`, `(session_id, created_at)`

role：

```
user

assistant

tool

system
```

------

# 9. LangGraph State持久化

## 9.1 checkpoint

用途：

保存Agent运行状态（MySQL 后端）。

LangGraph Checkpoint 表（由 LangGraph 自动管理）：

| 字段          | 说明          |
| ------------- | ------------- |
| thread_id     | 会话ID        |
| checkpoint_id | Checkpoint ID |
| parent_id     | 父Checkpoint  |
| state         | State JSON    |
| metadata      | 元数据        |
| created_at    | 创建时间      |

内容（state JSON）：

```
{
 "session_id":"",
 "current_node":"",
 "intent":"",
 "route_type":"",
 "summary":"",
 "pending_action":""
}
```

支持：

- Workflow恢复
- 中断继续
- 多轮任务

------

# 10. Memory设计

系统采用三级Memory。

------

## 10.1 Session Memory

存储：

当前Agent运行状态。

位置：

LangGraph Checkpoint

内容：

```
当前节点

当前任务

临时上下文
```

------

## 10.2 Summary Memory

用途：

保存历史对话摘要。

表：

```
conversation_summary
```

字段：

| 字段       | 类型     | 说明 | 索引 |
| ---------- | -------- | ---- | ---- |
| id         | bigint   | ID   | PK   |
| user_id    | bigint   | 用户 | IDX  |
| session_id | varchar  | 会话 | IDX  |
| summary    | text     | 摘要 |      |
| version    | int      | 版本 |      |
| created_at | datetime | 时间 |      |

索引设计：IDX: `user_id`, `session_id`, `(user_id, session_id)`

------

## 10.3 Long-term Memory

表：

```
user_memory
```

字段：

| 字段        | 类型     | 说明 | 索引 |
| ----------- | -------- | ---- | ---- |
| id          | bigint   | ID   | PK   |
| user_id     | bigint   | 用户 | IDX  |
| memory_type | varchar  | 类型 |      |
| content     | text     | 内容 |      |
| status      | tinyint  | 状态 |      |
| created_at  | datetime | 时间 |      |
| updated_at  | datetime | 时间 |      |

索引设计：IDX: `user_id`, `(user_id, memory_type, status)`

例如：

```
{
"type":"device_preference",
"content":"用户主要使用XXX设备"
}
```

要求：

必须：

user_id过滤。

禁止：

跨用户检索Memory。

------

## 10.4 RBAC 权限表

### 10.4.1 user_role

用途：

用户-角色关联。

字段：

| 字段    | 类型    | 说明 | 索引 |
| ------- | ------- | ---- | ---- |
| id      | bigint  | ID   | PK   |
| user_id | bigint  | 用户 | IDX  |
| role_id | bigint  | 角色 | IDX  |

索引设计：UK: `(user_id, role_id)`

------

### 10.4.2 role

用途：

角色定义。

字段：

| 字段        | 类型    | 说明     | 索引 |
| ----------- | ------- | -------- | ---- |
| id          | bigint  | 角色ID   | PK   |
| name        | varchar | 角色名   | UK   |
| description | varchar | 描述     |      |
| permissions | json    | 权限列表 |      |

permissions JSON 示例：

```json
{
  "knowledge": ["read", "write"],
  "prompts": ["read"],
  "users": ["read"]
}
```

------

### 10.4.3 knowledge_permission

用途：

知识库文档级权限控制。

字段：

| 字段        | 类型    | 说明         | 索引 |
| ----------- | ------- | ------------ | ---- |
| id          | bigint  | ID           | PK   |
| document_id | bigint  | 文档ID       | IDX  |
| role_id     | bigint  | 可访问角色   | IDX  |
| permission  | varchar | read / write |      |

索引设计：UK: `(document_id, role_id)`

------

# 11. 知识库数据设计

知识库主要存储于 Qdrant（Vector DB）。

MySQL 保存元数据。

------

## 11.1 knowledge_document

字段：

| 字段        | 说明     | 索引 |
| ----------- | -------- | ---- |
| id          | 文档ID   | PK   |
| name        | 文档名称 |      |
| device_type | 设备类型 | IDX  |
| doc_type    | 文档类型 | IDX  |
| version     | 版本     |      |
| permission  | 权限级别 |      |
| created_at  | 时间     |      |
| updated_at  | 时间     |      |

索引设计：IDX: `device_type`, `doc_type`, `(device_type, doc_type, version)`

------

## 11.2 knowledge_chunk

字段：

| 字段        | 说明     | 索引 |
| ----------- | -------- | ---- |
| id          | Chunk ID | PK   |
| document_id | 文档     | IDX  |
| content     | 文本     |      |
| chunk_index | 分块序号 |      |
| metadata    | JSON     |      |
| vector_id   | 向量ID   | UK   |

metadata JSON 与文档级 metadata 一致（继承自 knowledge_document）。

索引设计：IDX: `document_id`

Qdrant（Vector DB）：

保存：

```
embedding（向量）
```

MySQL：

保存：

```
metadata（元数据）
chunk信息（内容备份）
```

------

# 12. Trace数据设计

用于Agent链路追踪。

------

## 12.1 agent_trace

字段：

| 字段          | 说明   | 索引 |
| ------------- | ------ | ---- |
| id            | ID     | PK   |
| trace_id      | 请求ID | UK   |
| session_id    | 会话   | IDX  |
| user_id       | 用户   | IDX  |
| start_time    | 开始   |      |
| end_time      | 结束   |      |
| total_latency | 耗时   |      |
| status        | 状态   |      |

索引设计：

- PK: `id`
- UK: `trace_id`
- IDX: `session_id`, `user_id`, `(user_id, start_time)`

------

## 12.2 agent_trace_node

保存每个节点执行信息。

字段：

| 字段      | 说明   | 索引 |
| --------- | ------ | ---- |
| id        | ID     | PK   |
| trace_id  | 链路ID | IDX  |
| node_name | 节点   |      |
| input     | 输入   |      |
| output    | 输出   |      |
| latency   | 耗时   |      |

索引设计：

- PK: `id`
- IDX: `trace_id`, `(trace_id, node_name)`

节点：

例如：

```
safety_check

intent_classify

rag_retrieve

tool_execute

answer_generate
```

------

## 12.3 llm_call_record

记录模型调用。

字段：

| 字段              | 说明      | 索引 |
| ----------------- | --------- | ---- |
| id                | ID        | PK   |
| trace_id          | 链路      | IDX  |
| task_type         | 任务      |      |
| model_name        | 模型      |      |
| prompt_tokens     | 输入Token |      |
| completion_tokens | 输出Token |      |
| latency           | 耗时(ms)  |      |
| created_at        | 时间      |      |

索引设计：

- PK: `id`
- IDX: `trace_id`, `(task_type, model_name)`, `(created_at)`

用于：

- Model Routing优化
- 成本分析

------

# 13. Redis数据设计

Redis用于高频临时数据。

------

# 13.1 限流

Key：

```
rate_limit:{action}:{user_id}
```

例如：

```
rate_limit:create_ticket:10001
```

用途：

限制：

- 创建工单
- 转人工
- 高频请求

------

# 13.2 分布式锁

Key：

```
lock:{action}:{user_id}:{device_sn}
```

例如：

```
lock:create_ticket:user1001:SN001
```

防止：

- 重复创建工单
- 重复提交

------

# 13.3 Session缓存

Key：

```
session:{session_id}
```

保存：

- 当前状态
- 临时上下文

------

# 14. Qdrant（Vector Database）设计

Qdrant 用于语义检索。

## Collection 设计

### 14.1 企业知识库 Collection

名称：`enterprise_knowledge`

内容：

- 说明书
- FAQ
- 故障码
- 政策文档

Metadata：

```
{
"device_type":"",
"doc_type":"",
"version":"",
"permission":"",
"document_id":""
}
```

检索时强制携带 metadata 过滤条件。

------

### 14.2 用户 Summary Collection

名称：`user_summary`

独立 Collection。

Metadata：

```
{
"user_id":""
}
```

必须：

查询时携带 `user_id` 过滤。禁止跨用户检索。

------

### 14.3 Qdrant 连接配置

```
host: localhost
port: 6333
api_key: <from env>
```

------

# 15. 数据安全设计

## 用户隔离

所有：

- 会话
- Memory
- 设备
- 工单

必须关联：

```
user_id
```

------

## 权限控制

知识库检索必须过滤：

```
permission

device_type

version
```

------

## 敏感信息

禁止：

- 明文保存敏感数据
- 日志记录用户隐私信息

------

# 16. 数据生命周期

## 对话数据

长期保存：

- 会话
- Trace
- Summary

## 临时数据

Redis：

自动过期。

## Vector数据

文档更新：

重新：

```
Chunk

↓

Embedding

↓

Update Vector
```

------

# 总结

系统采用：

MySQL + Redis + Vector DB

多存储架构。

其中：

MySQL负责业务和长期数据，

Redis负责实时状态和工程保护，

Vector DB负责语义检索。

通过用户隔离、Metadata过滤、Trace记录和Checkpoint机制，

保证Agent系统：

- 可恢复
- 可追踪
- 可扩展
- 安全可靠。