# 系统架构设计文档

## 1. 文档概述

本文档描述医疗设备智能语音客服 Agent 平台整体系统架构。

系统基于：

- FastAPI
- LangGraph
- LangChain
- RAG
- Tool Calling
- Redis
- MySQL
- Qdrant（向量数据库）
- WebSocket
- FunASR + SenseVoice（语音识别）
- CosyVoice 2（语音合成）
- DeepSeek（LLM）

构建面向医疗设备售后场景的企业级 Agent 系统。


区别于传统：

用户 -> LLM -> Answer

的简单 ChatBot 模式。


本系统采用：

用户输入
↓
安全检查
↓
意图识别
↓
Agent Workflow路由
↓
知识检索 / 工具调用 / 人工确认
↓
回答生成
↓
安全校验
↓
Memory更新


实现：

- 可控
- 可追踪
- 可回退
- 可评估

的业务型 Agent 架构。



---

# 2. 整体架构


```text

                    用户
                     |
        ┌────────────┴────────────┐
        |
    Web / APP / 电话系统
        |
        |
   ASR语音识别
        |
        |
   WebSocket Gateway
        |
        |
===============================
        FastAPI Service
===============================

        |
        |
  Input Safety Check
        |
        |
  Intent Classification
        |
        |
  Query Router
        |
        |
 =====================
 |                   |
RAG Retrieval     Tool Calling
 |                   |
 |                   |
知识库             Tool Registry
 |                   |
 |                   |
Vector DB        Tool Executor
                     |
                     |
              Human Confirm
                     |
                     |
              Business System


        |
        |
 Answer Generation

        |
        |
 Output Guardrails

        |
        |
 Memory Update


        |
        |
 Trace / Eval System
```



------

# 3. 分层架构

系统整体分为六层：

```
┌─────────────────────────┐
│       接入层             │
│ Web APP / 电话 / ASR/TTS │
└────────────┬────────────┘

             |

┌─────────────────────────┐
│       服务层             │
│ FastAPI API Gateway     │
└────────────┬────────────┘

             |

┌─────────────────────────┐
│       Agent层            │
│ LangGraph Workflow      │
└────────────┬────────────┘

             |

┌─────────────────────────┐
│       能力层             │
│ RAG / Tool / Memory     │
└────────────┬────────────┘

             |

┌─────────────────────────┐
│       数据层             │
│ MySQL Redis Vector DB   │
└────────────┬────────────┘

             |

┌─────────────────────────┐
│       可观测层           │
│ Trace / Eval / Logging  │
└─────────────────────────┘
```

------

# 4. 接入层

## 4.1 用户入口

支持：

- Web客服
- 移动端
- 电话客服

语音场景：

```
用户语音

↓

ASR（FunASR + SenseVoice）

↓

文本Query

↓

Agent处理

↓

TTS（CosyVoice 2）

↓

语音回复
```

## 4.2 WebSocket通信

WebSocket负责：

- 实时消息传输
- 流式回答
- ASR结果推送
- Agent状态同步

支持：

- SSE流式输出
- WebSocket双向通信

------

# 5. FastAPI服务层

FastAPI作为系统入口。

主要职责：

- 用户请求接收
- Session管理
- 参数校验
- 权限验证
- 调用Agent Workflow
- 返回流式结果

接口职责：

```
API

↓

Service

↓

Agent

↓

Tool/RAG
```

禁止：

API层直接调用LLM。

------

# 6. Agent Workflow层

核心使用：

LangGraph

负责：

- 状态管理
- 节点编排
- 条件分支
- Checkpoint恢复
- Workflow追踪

核心流程：

```
Input

 ↓

Safety Check

 ↓

Intent Classify

 ↓

Context Load

 ↓

Query Router

 ↓

 ┌───────────────┐
 │               │
RAG             Tool

 │               │

Answer        Confirm

 └───────┬───────┘

         |

Response Generate

         |

Output Safety

         |

Memory Update
```

Agent层不直接实现业务。

例如：

创建工单：

Agent只负责：

判断用户需要创建工单

↓

生成Tool参数

真正执行：

Tool Executor负责。

------

# 7. RAG知识检索架构

## 7.1 企业知识库

存储：

- 产品说明书
- FAQ
- 故障码
- 售后政策
- 操作文档

流程：

```
Document

↓

Parser

↓

Chunk

↓

Embedding

↓

Vector DB

↓

Retriever

↓

Context
```

------

## 7.2 Metadata过滤

所有知识必须携带：

```
{
 "device_type":"",
 "doc_type":"",
 "version":"",
 "permission":""
}
```

检索流程：

```
User Query

↓

Intent

↓

Metadata Filter

↓

Vector Search

↓

TopK Documents

↓

LLM Answer
```

目的：

避免：

- 不同设备资料混淆
- 不同版本文档冲突
- 权限越界

------

# 8. Tool Calling架构

Tool负责连接企业业务系统。

架构：

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

当前支持：

| Tool                   | 功能         |
| ---------------------- | ------------ |
| query_warranty         | 保修查询     |
| query_device_binding   | 查询设备绑定 |
| create_ticket          | 创建工单     |
| transfer_human         | 转人工       |

执行流程：

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

User Confirm

↓

Execute
```

------

# 9. Memory架构

系统采用多级Memory。

## 9.1 Session Memory

保存：

当前对话状态。

实现：

LangGraph Checkpoint

内容：

- 当前State
- 当前Intent
- 当前任务

------

## 9.2 Summary Memory

保存：

历史对话摘要。

存储：

MySQL

用于：

长对话上下文压缩。

------

## 9.3 Long-term Memory

保存：

用户长期有效信息。

例如：

- 用户设备
- 历史问题
- 服务记录

必须：

user_id隔离。

禁止：

用户之间共享Memory。

------

# 10. 数据存储架构

系统包含三类存储。

## MySQL

负责：

业务数据：

- 用户
- 设备
- 工单
- 会话
- Trace
- Summary

------

## Redis

负责：

高性能临时数据：

- Session缓存
- 限流
- 分布式锁

例如：

```
rate_limit:create_ticket:user_id

lock:create_ticket:user_id:device_sn
```

------

## Qdrant (Vector Database)

负责：

语义检索。

存储：

- 文档Embedding
- 用户Summary Embedding

必须：

metadata隔离。

Collection 设计：

- `enterprise_knowledge`：企业公共知识库
- `user_summary`：用户历史摘要（按 user_id 隔离）

------

# 11. 安全架构

医疗客服场景增加安全层。

## 输入安全

检测：

- 医疗诊断请求
- 治疗建议
- 隐私请求

## 输出安全

检测：

- 错误医疗建议
- 无依据承诺
- 越权回答

风险流程：

```
High Risk

↓

Safe Reply

or

Human Service
```

------

# 12. 可观测架构

Trace系统记录完整链路。

一次请求包含：

```
trace_id

User Query

↓

Intent

↓

Router

↓

RAG Result

↓

Tool Call

↓

Model

↓

Prompt

↓

Response
```

用于分析：

- RAG召回错误
- Tool失败
- Prompt问题
- 模型选择问题
- 延迟问题

------

# 13. 部署架构

推荐部署：

```
                Nginx

                  |

              FastAPI

                  |

        --------------------

        |        |          |

    Agent    Redis      MySQL

        |

     Qdrant

        |

  DeepSeek API
```

------

# 14. 架构设计原则

## 可控性

所有高风险动作必须经过：

- Schema校验
- 权限检查
- 用户确认

------

## 可观察

所有Agent节点必须支持：

Trace记录。

------

## 可扩展

新增能力：

通过新增：

- Node
- Tool
- Prompt

扩展。

------

## 安全优先

医疗场景：

宁可拒答，也不能生成错误医疗建议。

------

# 总结

本系统采用：

FastAPI + LangGraph + RAG + Tool Calling + Memory + Guardrails

构建企业级医疗设备智能客服Agent。

整体架构由：

- 接入层
- 服务层
- Agent Workflow层
- 能力层
- 数据层
- 可观测层

组成，实现从传统知识问答系统向可执行、可控制、可追踪的智能客服Agent平台升级。