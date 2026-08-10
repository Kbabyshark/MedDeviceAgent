# Agent Workflow设计文档

## 1. 文档概述


本文档描述医疗设备智能客服 Agent 的核心 Workflow 设计。


系统基于：

- LangGraph
- LangChain
- RAG
- Tool Calling
- Human-in-the-loop


将传统：

用户问题

↓

LLM

↓

回答

```
升级为：
```

输入理解

↓

风险控制

↓

意图识别

↓

动态路由

↓

知识检索 / 工具执行

↓

用户确认

↓

回答生成

↓

记忆更新

↓

Trace记录的企业级 Agent Workflow。


---

# 2. 整体Workflow架构


```text

                 User Input

                     |

                     v

            +----------------+

            | Safety Check   |

            +----------------+

                     |

                     v

            +----------------+

            | Intent Router  |

            +----------------+

                     |

                     v

            +----------------+

            | Query Router   |

            +----------------+

                     |

        +------------+-------------+

        |                          |

        v                          v


   RAG Workflow              Tool Workflow


        |                          |

        v                          v


 Knowledge Search          Tool Registry


        |                          |

        v                          v


 Answer Generate          Human Confirm


        |                          |

        +------------+-------------+

                     |

                     v


          Output Safety Check


                     |

                     v


          Memory Update


                     |

                     v


              Final Response
```

------

# 3. LangGraph State设计

Agent通过State在节点之间传递上下文。

核心State：

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

------

# 4. Node设计

Workflow拆分为多个独立Node。

------

# 4.1 Input Safety Check Node

节点：

```
input_safety_check_node
```

职责：

检测用户输入风险。

检测：

- 医疗诊断请求
- 治疗建议
- 用药问题
- 隐私攻击
- 越权请求

输入：

```
user query
```

输出：

```
{
 "risk_level":"high",
 "pass":false
}
```

分支：

```
High Risk

↓

safe_reply_node


Normal

↓

intent_classify_node
```

------

# 4.2 Intent Classification Node

节点：

```
intent_classify_node
```

职责：

识别用户业务意图。

采用：

规则 + LLM

流程：

```
User Query

↓

AC自动机匹配

↓

命中

直接返回Intent


未命中

↓

LLM结构化分类
```

Intent类型：

```
faq_query

device_info_query

fault_code_query

troubleshooting

warranty_query

device_binding

create_ticket

transfer_human

medical_risk
```

输出：

```
{
 "intent":"fault_code_query"
}
```

------

# 4.3 Context Load Node

节点：

```
context_load_node
```

职责：

加载用户上下文。

数据来源：

- Session Memory
- Summary Memory
- 用户设备信息

流程：

```
session_id

↓

Checkpoint

↓

summary

↓

device_info
```

注意：

用户Memory必须：

```
user_id过滤
```

防止：

用户数据串扰。

------

# 4.4 Query Router Node

节点：

```
query_router_node
```

职责：

决定后续执行路径。

根据：

- intent
- route_type
- risk_level
- query复杂度

动态选择。

------

路由规则：

| Intent     | Route         |
| ---------- | ------------- |
| FAQ        | RAG           |
| 故障码     | RAG           |
| 说明书查询 | RAG           |
| 保修查询   | Tool          |
| 设备绑定   | Tool          |
| 创建工单   | Tool + Human  |
| 转人工     | Tool + Human  |
| 简单闲聊   | Direct Answer |
| 高风险     | Safe Reply    |

输出：

```
{
 "route_type":"rag"
}
```

------

## 4.5 Multi-Intent Handling（多意图处理）

当用户一次输入包含多个意图时（如 "E101 是什么？并且帮我申请维修"），系统按以下策略处理：

### 识别阶段

Intent Classify Node 返回意图列表及置信度：

```
{
  "intents": [
    {"intent": "fault_code_query", "confidence": 0.95},
    {"intent": "create_ticket", "confidence": 0.88}
  ]
}
```

### 路由策略

| 场景 | 策略 | 说明 |
|------|------|------|
| 多个 RAG 意图 | 串行检索，合并去重 | 同一设备上下文下检索，结果合并 |
| RAG + Tool（查询） | 并行执行 | 检索不影响查询，互不依赖 |
| RAG + Tool（写操作） | 串行执行 | 先回答知识问题，再进入 Human Confirm |
| 包含 medical_risk | 中断，进入 Safe Reply | 医疗风险优先拦截 |
| 包含 transfer_human | 优先转人工 | 其他意图作为上下文摘要传递给客服 |

### 合并回答

```
RAG 结果 + Tool 查询结果

        ↓

Answer Generate Node

        ↓

统一回答（先回答知识，再展示业务结果）
```

多意图中任一需要 Human Confirm 时，先输出已回答部分，再展示待确认操作。

------

# 5. RAG Workflow

## 5.1 RAG流程

```
Query

 |

Query Rewrite

 |

Metadata Filter

 |

Embedding

 |

Vector Search

 |

Top-K Retrieval (K=20)

 |

Rerank（重排序，返回 Top-N，N=5）

 |

Context Build

 |

LLM Answer
```

------

# 5.2 Query Rewrite Node

节点：

```
query_rewrite_node
```

作用：

优化用户问题。

例如：

用户：

```
E101是什么
```

转换：

```
查询设备型号XXX出现E101故障原因和处理步骤
```

------

# 5.3 Retriever Node

节点：

```
rag_retrieve_node
```

检索条件：

```
{
 "device_type":"",
 "doc_type":"",
 "version":"",
 "permission":""
}
```

避免：

- 跨设备召回
- 文档版本冲突
- 权限泄露

------

## 5.3.1 Rerank 策略

节点：

```
rag_rerank_node
```

Rerank 模型：

使用 DeepSeek-R1 或专用 Rerank 模型（如 BGE-Reranker）对 Top-K 结果进行重排序。

Rerank 触发条件：

| 场景 | 是否 Rerank | 说明 |
|------|------------|------|
| Top-1 相似度 > 0.9 | 跳过 | 高置信度直接使用 |
| Top-1 相似度 0.6-0.9 | 执行 | 正常范围，Rerank 提升精度 |
| Top-1 相似度 < 0.6 | 执行 + 降级提示 | 低置信度，告知用户信息可能不准确 |
| 多个文档来源混合 | 执行 | 需要重排序去重 |

Rerank 后保留 Top-N（N=5）进入 Context Build。

------

# 5.4 RAG Answer Node

节点：

```
rag_answer_node
```

输入：

- 用户问题
- 检索文档
- 历史摘要

输出：

最终回答。

要求：

回答必须：

- 基于检索内容
- 不编造
- 保留引用信息

------

# 6. Tool Workflow

## 6.1 Tool调用架构

```
Agent

 |

Tool Registry

 |

Tool Executor

 |

Business API

 |

Database
```

------

# 6.2 Tool Registry

统一管理工具。

例如：

```
tools = [

 query_warranty,

 query_device_binding,

 create_ticket,

 transfer_human

]
```

------

# 6.3 Tool Execute Node

节点：

```
tool_execute_node
```

执行前：

必须经过：

```
Tool Parameter Schema

↓

Permission Check

↓

Risk Check

↓

Human Confirm

↓

Execute
```

------

# 7. Human-in-the-loop Workflow

用于高风险操作。

场景：

- 创建维修工单
- 转人工
- 修改业务数据

流程：

```
Agent

 |

生成操作建议

 |

pending_action写入State

 |

等待用户确认

 |

用户确认

 |

Tool Execute
```

State：

```
{
 "pending_action":{

 "type":"create_ticket",

 "params":{}

 }

}
```

用户：

确认：

```
execute
```

取消：

```
cancel
```

------

# 8. Answer Generation Workflow

节点：

```
answer_generate_node
```

输入：

- RAG结果
- Tool结果
- Conversation Context

输出：

用户最终回答。

规则：

```
如果Tool成功

↓

返回业务结果


如果RAG

↓

返回知识答案


如果风险

↓

安全回复
```

------

# 9. Output Guardrails

节点：

```
output_safety_check_node
```

检查：

- 医疗建议
- 虚假承诺
- 越权信息
- 敏感数据

流程：

```
Answer

↓

Safety Check

↓

Pass

↓

User


Fail

↓

Safe Reply
```

------

# 10. Memory Workflow

## 10.1 Session Memory

存储：

当前任务状态。

实现：

LangGraph Checkpoint。

------

## 10.2 Summary Memory

长对话：

```
Messages

↓

Summary

↓

压缩Context
```

触发：

- Token超过阈值
- 对话轮数超过限制

------

## 10.3 Long Term Memory

流程：

```
Conversation

↓

Memory Extract

↓

Filter

↓

Store
```

保存：

- 用户设备偏好
- 历史服务信息

------

# 11. Model Routing Workflow

节点：

```
model_router_node
```

根据：

- task_type
- risk_level
- token长度
- 成本

选择模型。

规则：

| 任务         | 模型                | 说明 |
| ------------ | ------------------- | ---- |
| Intent分类   | DeepSeek-V3         | 低延迟，结构化输出 |
| Summary      | DeepSeek-V3         | 低延迟 |
| RAG回答      | DeepSeek-R1         | 高推理能力 |
| 复杂故障分析 | DeepSeek-R1         | 高推理能力 |
| Safety       | DeepSeek-V3 + 规则  | 低延迟优先，规则兜底 |

------

# 12. Trace Workflow

每个Node执行时记录：

```
{
"trace_id":"xxx",

"node":"rag_retrieve",

"input":{},

"output":{},

"latency":300

}
```

记录：

- Node输入输出
- Prompt版本
- Model
- Token
- RAG结果
- Tool参数
- 错误信息

支持：

```
trace_id

↓

完整Workflow回放
```

------

# 13. 异常处理机制

## RAG失败

情况：

- 无召回
- 低置信度

处理：

```
Retry

↓

Query Rewrite

↓

Fallback Answer
```

------

## Tool失败

处理：

```
记录错误

↓

返回用户友好提示

↓

人工接管
```

------

## LLM失败

处理：

```
Model Retry

↓

Fallback Model

↓

Safe Response
```

------

# 14. 完整执行示例

用户：

```
我的设备显示E101，并且想申请维修
```

流程：

```
Input

↓

Safety Check

↓

Intent

识别:

fault_code_query + create_ticket


↓

Query Router


↓

RAG查询E101


↓

生成故障解释


↓

生成维修工单草稿


↓

pending_action


↓

用户确认


↓

Tool Create Ticket


↓

Output Check


↓

Memory Update


↓

返回结果
```

------

# 15. Workflow设计原则

## 单一职责

每个Node只负责一个任务。

------

## 状态驱动

所有上下文通过State传递。

------

## 可回退

失败节点支持：

Retry/Fallback。

------

## 可观测

每个节点必须Trace。

------

## 安全优先

高风险操作必须Human确认。

------

# 总结

医疗设备智能客服 Agent Workflow 通过 LangGraph 将：

- 意图理解
- 知识检索
- 工具调用
- 用户确认
- 安全控制
- Memory管理
- Trace分析

拆分为多个可控节点。

最终实现：

```
传统RAG

↓

业务型Agent Workflow


可理解

可执行

可控制

可追踪

可优化
```