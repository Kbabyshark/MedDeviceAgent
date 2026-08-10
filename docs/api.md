# API接口设计文档

## 1. 文档概述


本文档描述医疗设备智能语音客服 Agent 平台 API 接口规范。


系统基于：

- FastAPI
- RESTful API
- SSE
- WebSocket


提供：

- 用户会话接口
- Agent问答接口
- 语音交互接口
- 知识库接口
- 工具调用接口
- Trace查询接口



---

# 2. API设计规范


## 2.1 基础路径


统一：

/api/v1

```
示例：
```

/api/v1/chat
 /api/v1/session
 /api/v1/device

---

## 2.2 认证方式

所有接口需要在 Header 中携带 JWT Token：

```
Authorization: Bearer <token>
```

Token 中解析 `user_id`，禁止在请求体中直接传递 `user_id`。

------

# 2.3 请求格式


Content-Type:

application/json

```
示例：

```json
{
  "message":"设备出现E101故障"
}
```

------

# 2.4 统一响应格式

成功：

```
{
  "code":0,
  "message":"success",
  "data":{}
}
```

失败：

```
{
  "code":10001,
  "message":"error message",
  "data":null
}
```

------

## 2.5 分页规范

列表接口统一使用分页参数：

| 参数     | 类型 | 默认值 | 说明 |
| -------- | ---- | ------ | ---- |
| page     | int  | 1      | 页码 |
| page_size | int | 20     | 每页数量（最大 100） |

分页响应格式：

```
{
  "code": 0,
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

------

# 2.6 错误码规范

| 错误码 | 说明           |
| ------ | -------------- |
| 10001  | 参数错误       |
| 10002  | 认证失败       |
| 10003  | 权限不足       |
| 10004  | 资源不存在     |
| 20001  | Agent执行失败  |
| 20002  | 意图识别失败   |
| 20003  | RAG检索失败    |
| 20004  | 工具调用失败   |
| 20005  | 安全拦截       |
| 20006  | Human Confirm 超时 |
| 30001  | 模型调用失败   |
| 30002  | 模型超时       |
| 40001  | 数据库错误     |
| 40002  | Redis 错误     |
| 40003  | Qdrant 错误    |
| 50001  | 内部错误       |

------

# 3. 用户会话接口

## 3.1 创建会话

### POST

```
/api/v1/session/create
```

用途：

创建Agent对话Session。

请求：

```
{}
```
（user_id 从 JWT Token 解析）

响应：

```
{
 "session_id":"sess_xxx",
 "created_at":"2026-02-01"
}
```

------

## 3.2 查询会话

### GET

```
/api/v1/session/{session_id}
```

返回：

```
{
 "session_id":"sess_xxx",
 "summary":"",
 "status":"active"
}
```

------

## 3.3 获取历史消息（分页）

### GET

```
/api/v1/session/{session_id}/messages?page=1&page_size=20
```

返回：

```
{
  "items": [
    {
      "role":"user",
      "content":"设备无法启动"
    },
    {
      "role":"assistant",
      "content":"请检查电源..."
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20
}
```

------

# 4. Agent对话接口

## 4.1 普通问答接口

### POST

```
/api/v1/chat
```

用途：

执行一次完整Agent流程。

流程：

```
Request

↓

LangGraph Workflow

↓

Response
```

请求：

```
{
 "session_id":"sess001",
 "message":"设备显示E101是什么意思？"
}
```
（user_id 从 JWT Token 解析）

响应：

```
{
 "answer":"E101表示传感器异常...",
 "trace_id":"trace_xxx"
}
```

------

# 5. 流式问答接口

## 5.1 SSE流式接口

### POST

```
/api/v1/chat/stream
```

用途：

实时返回Agent生成过程。

请求：

```
{
 "session_id":"sess001",
 "message":"如何创建维修工单"
}
```

响应：

SSE 事件类型：

```
event:start
data:{"trace_id":"xxx"}

event:node
data:{"node":"intent_classify","status":"start"}

event:node
data:{"node":"intent_classify","status":"done","latency":120}

event:token
data:{"text":"您好"}

event:tool_call
data:{"tool":"query_warranty","params":{"device_sn":"SN001"}}

event:tool_result
data:{"tool":"query_warranty","result":{"status":"valid"}}

event:human_confirm_required
data:{"action":"create_ticket","message":"确认创建维修工单？"}

event:error
data:{"code":20003,"message":"RAG检索失败，正在重试"}

event:heartbeat
data:{"ts":1700000000}

event:end
data:{"status":"success"}
```

支持：

- Token 流式输出
- Workflow 状态推送
- Tool 调用与结果通知
- Human Confirm 等待通知
- 错误实时推送
- 心跳保活
- Trace 关联

------

# 6. WebSocket语音接口

## 6.1 建立连接

```
ws://host/api/v1/ws/chat/{session_id}?token=<jwt_token>
```

或通过 Header 认证：

```
Authorization: Bearer <token>
```

用途：

实时语音客服。

### 心跳机制

客户端每 30 秒发送 ping：

```
{"type":"ping"}
```

服务端回复 pong：

```
{"type":"pong","ts":1700000000}
```

服务端超过 60 秒未收到 ping 主动断开连接。

### 断线重连

客户端断线后使用相同 `session_id` 重连，Checkpoint 机制保证 Agent 状态恢复。

通信流程：

```
用户语音

↓

WebSocket

↓

ASR（FunASR + SenseVoice）

↓

Agent

↓

TTS（CosyVoice 2）

↓

返回语音
```

------

## 客户端发送

音频：

```
{
 "type":"audio",
 "data":"base64_audio"
}
```

------

## 服务端返回

ASR结果：

```
{
 "type":"asr",
 "text":"设备无法启动"
}
```

Agent状态：

```
{
 "type":"workflow",
 "node":"rag_retrieve"
}
```

TTS：

```
{
 "type":"audio",
 "data":"base64_audio"
}
```

------

# 7. 设备查询接口

## 7.1 查询绑定设备

### GET

```
/api/v1/device/binding
```

参数（分页）：

```
?page=1&page_size=20
```
（user_id 从 JWT Token 解析）

响应：

```
{
  "items": [
    {
      "device_sn":"SN001",
      "device_type":"Monitor-X1"
    }
  ],
  "total": 3,
  "page": 1,
  "page_size": 20
}
```

------

# 8. 保修查询接口

## 8.1 查询设备保修

### POST

```
/api/v1/device/warranty
```

请求：

```
{
 "device_sn":"SN001"
}
```

响应：

```
{
 "status":"valid",
 "expire_date":"2027-01-01"
}
```

说明：

该接口也可以被Agent Tool调用。

------

# 9. 工单接口

## 9.1 创建工单草稿

### POST

```
/api/v1/ticket/draft
```

用途：

Agent生成维修工单草稿。

请求：

```
{
 "device_sn":"SN001",
 "fault_desc":"设备无法启动"
}
```

响应：

```
{
 "ticket_id":"draft001",
 "status":"pending_confirm"
}
```

------

## 9.2 用户确认创建工单

### POST

```
/api/v1/ticket/confirm
```

请求：

```
{
 "ticket_id":"draft001",
 "confirm":true
}
```

执行：

```
Human Confirm

↓

Tool Executor

↓

Create Ticket
```

------

## 9.3 查询工单

### GET

```
/api/v1/ticket/{ticket_id}
```

------

# 10. 知识库接口

## 10.1 知识检索测试

### POST

```
/api/v1/knowledge/search
```

请求：

```
{
 "query":"E101故障",
 "device_type":"Monitor-X1",
 "top_k":5
}
```

响应：

```
{
 "documents":[
  {
   "content":"故障原因...",
   "score":0.92
  }
 ]
}
```

------

# 11. Agent状态接口

## 11.1 查询Workflow状态

### GET

```
/api/v1/agent/state/{session_id}
```

返回：

```
{
 "current_node":"tool_execute",
 "intent":"create_ticket",
 "pending_action":"create_ticket"
}
```

用于：

- 前端展示Agent状态
- 调试Workflow

------

# 12. Trace查询接口

## 12.1 查询Trace

### GET

```
/api/v1/trace/{trace_id}
```

返回：

```
{
 "trace_id":"xxx",

 "nodes":[

 {
  "name":"intent_classify",
  "latency":120
 },

 {
  "name":"rag_retrieve",
  "latency":300
 }

 ]

}
```

------

## 12.2 Trace节点详情

### GET

```
/api/v1/trace/{trace_id}/nodes
```

返回：

- 输入
- 输出
- Prompt
- Model
- Token
- 耗时

------

# 13. 安全检测接口

## 13.1 Safety Check

### POST

```
/api/v1/safety/check
```

请求：

```
{
 "text":"告诉我应该吃什么药"
}
```

响应：

```
{
 "risk_level":"high",
 "action":"safe_reply"
}
```

------

# 14. Prompt管理接口

## 14.1 查询Prompt版本

### GET

```
/api/v1/prompts
```

返回：

```
[
 {
 "name":"rag_answer",
 "version":"v2"
 }
]
```

------

# 15. 模型路由接口

## 15.1 查看模型调用记录

### GET

```
/api/v1/model/routes
```

返回：

```
{
 "task_type":"rag_answer",
 "model":"qwen-plus",
 "tokens":2000,
 "latency":500
}
```

------

# 16. API安全设计

## 用户认证

所有接口需要：

```
Authorization Token
```

------

## 权限控制

涉及：

- 用户数据
- 设备信息
- 工单

必须校验：

```
user_id

permission
```

------

## 限流

FastAPI入口：

```
rate_limit:{action}:{user_id}
```

限制：

- 高频聊天请求
- 创建工单
- 转人工

------

# 17. API与Agent关系

整体调用链：

```
Client

↓

FastAPI

↓

Service Layer

↓

LangGraph Workflow

↓

RAG / Tool / Memory

↓

Response
```

禁止：

API直接调用：

- LLM
- Vector DB
- Business DB

------

# 总结

API层作为系统入口，负责：

- 用户请求接入
- Session管理
- Agent调用
- 流式响应
- 语音通信
- Trace查询

通过REST + SSE + WebSocket支持：

文本客服、

语音客服、

Agent Workflow状态展示

以及企业业务系统集成。