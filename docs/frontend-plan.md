# 前端开发计划

## 概述

基于已完成的 Agent 后端平台，构建面向用户和管理员的 Web 前端。

**技术选型**：
- 框架：Vue 3（Composition API）+ TypeScript
- 构建：Vite
- UI：Tailwind CSS + Naive UI（组件库，医疗场景风格适配好）
- 状态管理：Pinia（页面级）/ Vue Query（服务端状态）
- 路由：Vue Router 4
- HTTP：fetch + SSE（流式）/ 原生 WebSocket（语音）
- 语音：浏览器 Web Audio API + MediaRecorder

**设计原则**：
- 医疗场景：清爽、专业、高可读性
- 语音优先：移动端一键语音输入
- 流式展示：Agent 思考过程可视化
- 安全第一：医疗风险内容高亮提示

---

## 全景路线图

```
Round 1          Round 2          Round 3          Round 4
基础框架 ────→ 文本客服 ────→ 语音客服 ────→ 管理后台
  │                │                │                │
  │ 项目脚手架     │ 聊天界面       │ 语音输入       │ 知识库管理
  │ 路由/布局      │ SSE 流式       │ WebSocket      │ Trace 查看
  │ API 层         │ 会话管理       │ 语音输出       │ 成本仪表板
  │ 组件库         │ 工单确认       │ 心跳重连       │ 系统监控
  └────────────────┴────────────────┴────────────────┘
                                       │
                                  Round 5
                                  移动端适配 ────→ PWA + 响应式
```

---

# Round 1: 基础框架搭建

## 目标

项目脚手架就绪，路由、布局、API 层、基础组件可用。

## 任务清单

| # | 任务 | 预期产出 |
|---|------|---------|
| 1.1 | Vite + Vue 3 + TypeScript 项目初始化 | `npm run dev` 可启动 |
| 1.2 | Tailwind CSS + Naive UI 配置 | 主题系统（医疗场景配色） |
| 1.3 | 路由设计：`/chat` `/history` `/admin/*` | Vue Router 4 路由表 + 导航守卫 |
| 1.4 | 布局组件：Sidebar + Header + Main | 响应式布局骨架 |
| 1.5 | API 客户端封装（fetch + JWT 拦截 + 错误处理） | `apiClient.get/post/stream()` |
| 1.6 | 认证页面：登录 / 注册 | JWT Token 存储 + Pinia authStore |
| 1.7 | 全局 Loading / Toast / ErrorBoundary | Naive UI Message / Dialog 集成 |
| 1.8 | TypeScript 类型定义（对齐后端 Schema） | `types/` 目录 |

## 验收条件

```
✅ 登录成功 → 跳转 /chat
✅ 未登录访问 → 重定向 /login
✅ 侧边栏折叠/展开 + 移动端隐藏
✅ API 请求自动携带 Authorization Header
✅ 网络错误 → Toast 提示
```

---

# Round 2: 文本客服核心

## 目标

文本对话界面完整可用：发送消息 → SSE 流式展示 → 会话管理。

## 任务清单

| # | 任务 | 预期产出 |
|---|------|---------|
| 2.1 | 聊天主界面：消息列表 + 输入框 + 发送按钮 | Bubble 样式消息组件 |
| 2.2 | SSE 流式接收 + Markdown 渲染 | 逐字展示 Agent 回复 |
| 2.3 | Agent 状态指示器 | "思考中…" / "检索知识库…" / "生成回答…" |
| 2.4 | 引用来源展示（Citation Card） | 每条回答底部显示知识库来源 |
| 2.5 | 会话创建 / 切换 / 删除 | 侧边栏会话列表 |
| 2.6 | 历史消息加载（分页 + 滚动加载更多） | 上滑加载历史 |
| 2.7 | 工单确认流程 | pending_action 卡片 + 确认/取消按钮 |
| 2.8 | 医疗风险提示 | 高风险回答黄色背景 + 警告图标 |
| 2.9 | 快捷键支持 | Enter 发送 / Shift+Enter 换行 |

## 验收条件

```
✅ 发送"E101是什么" → SSE 逐字展示回答 → Citation 显示来源
✅ 发送"帮我报修" → 弹出确认卡片 → 点确认 → 工单创建成功
✅ 发送"我该吃什么药" → 黄色警告样式 → 安全回复
✅ 切换会话 → 加载该会话历史消息
✅ 上滑 → 加载更早的消息
```

---

# Round 3: 语音客服

## 目标

Web 端语音输入/输出完整可用。

## 任务清单

| # | 任务 | 预期产出 |
|---|------|---------|
| 3.1 | 语音录制 Composable（MediaRecorder + AudioContext） | `useVoiceRecorder()` |
| 3.2 | 语音播放 Composable（AudioContext 解码播放） | `useAudioPlayer()` |
| 3.3 | WebSocket 语音连接管理 | `useVoiceWebSocket()` 自动连接 / 心跳 / 断线重连 |
| 3.4 | 语音按钮（按住说话 / 松开发送） | 移动端长按录音 |
| 3.5 | ASR 实时文本回显 | 录音时实时显示识别文本 |
| 3.6 | TTS 音频流播放 | 收到 TTS chunk → 自动排队播放 |
| 3.7 | 语音 + 文本混合模式 | 同一会话内可切换输入方式 |
| 3.8 | 语音权限处理 + 降级提示 | 无麦克风 → 自动切文本模式 |

## 验收条件

```
✅ 按住语音按钮 → 录音 → 松开 → WebSocket 发送
✅ 识别文本实时回显在输入框
✅ Agent 回复 → 自动 TTS 播放
✅ 播放中发送新消息 → 中断当前播放
✅ 断线 → 自动重连 → session 恢复
```

---

# Round 4: 管理后台

## 目标

管理员可通过 Web 界面管理知识库、查看 Trace、监控成本。

## 任务清单

| # | 任务 | 预期产出 |
|---|------|---------|
| 4.1 | 管理后台布局 + 路由守卫（仅 admin 可见） | `/admin/*` 需 admin 角色 |
| 4.2 | 知识库文档列表 + 筛选 + 分页 | 表格组件 |
| 4.3 | 文档上传对话框（拖拽 + 文件选择） | 上传进度条 + 处理状态 |
| 4.4 | 文档版本管理（上传新版本 / 查看历史） | 版本时间线 |
| 4.5 | 知识检索测试面板 | 输入 query → 显示 Top-K 结果 + score |
| 4.6 | Trace 查询 + 节点时间线 | 按 trace_id 搜索 → 瀑布图展示 |
| 4.7 | Trace 回放播放器 | Step-by-step 动画展示 Workflow 过程 |
| 4.8 | 成本仪表板（折线图 + 汇总卡片） | Token 趋势 + 费用估算 |
| 4.9 | 系统状态面板（P95 延迟 + 告警列表） | 实时刷新 |

## 验收条件

```
✅ 上传 PDF → 进度条 100% → 文档列表出现 → 状态变为 ready
✅ 知识检索测试 → 输入 query → 返回 Top-5 结果 + 相似度
✅ 输入 trace_id → 显示完整节点链路 + 每节点耗时
✅ 回放播放器 → 逐步展示 Workflow 执行过程
✅ 成本仪表板 → 显示 30 天 Token 趋势图
✅ 普通用户访问 /admin → 403
```

---

# Round 5: 移动端适配 + PWA

## 目标

移动端体验完善，可添加到主屏幕。

## 任务清单

| # | 任务 | 预期产出 |
|---|------|---------|
| 5.1 | 移动端响应式布局 | 所有页面适配 375px-768px |
| 5.2 | 移动端聊天界面优化 | 全屏聊天 + 底部输入栏 |
| 5.3 | PWA 配置（manifest + Service Worker） | 可添加到主屏幕 |
| 5.4 | 离线提示 + 网络状态监听 | 断网 Toast 提示 |
| 5.5 | 移动端手势优化 | 右滑返回 / 下拉刷新 |
| 5.6 | 暗色模式支持 | Tailwind dark mode |

## 验收条件

```
✅ iPhone/Android Chrome 访问 → 布局正常
✅ 添加到主屏幕 → 独立窗口打开（无浏览器工具栏）
✅ 离线状态 → 显示"网络连接异常"
✅ 暗色模式切换 → 所有页面跟随
```

---

## 里程碑总览

| Round | 名称 | 核心交付 | 周期 |
|-------|------|---------|------|
| **R1** | 基础框架 | 项目脚手架 + 路由 + API 层 + 登录 | 1 周 |
| **R2** | 文本客服 | 聊天界面 + SSE 流式 + 会话 + 工单确认 | 2 周 |
| **R3** | 语音客服 | 语音录制/播放 + WebSocket + ASR/TTS | 1.5 周 |
| **R4** | 管理后台 | 知识库 CRUD + Trace 回放 + 成本仪表板 | 2 周 |
| **R5** | 移动端 | 响应式 + PWA + 暗色模式 | 1 周 |

## 目录结构

```
frontend/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── package.json
├── public/
│   ├── manifest.json          # PWA manifest
│   └── sw.js                  # Service Worker
└── src/
    ├── main.ts                # 入口
    ├── App.vue                # 路由根组件
    ├── api/
    │   ├── client.ts          # fetch 封装 + JWT
    │   ├── chat.ts            # chat / stream
    │   ├── session.ts         # 会话 CRUD
    │   ├── ticket.ts          # 工单
    │   ├── knowledge.ts       # 知识库
    │   └── trace.ts           # Trace
    ├── composables/
    │   ├── useSSE.ts          # SSE 流式接收
    │   ├── useVoiceRecorder.ts
    │   ├── useAudioPlayer.ts
    │   ├── useWebSocket.ts    # 语音 WS
    │   └── useAuth.ts         # 认证状态
    ├── pages/
    │   ├── Login.vue
    │   ├── chat/
    │   │   ├── ChatPage.vue
    │   │   ├── MessageList.vue
    │   │   ├── MessageBubble.vue
    │   │   ├── ChatInput.vue
    │   │   ├── VoiceButton.vue
    │   │   ├── CitationCard.vue
    │   │   └── PendingAction.vue
    │   ├── admin/
    │   │   ├── AdminLayout.vue
    │   │   ├── KnowledgePage.vue
    │   │   ├── TracePage.vue
    │   │   ├── TraceReplay.vue
    │   │   ├── CostDashboard.vue
    │   │   └── StatusPage.vue
    │   └── NotFound.vue
    ├── components/
    │   ├── layout/
    │   │   ├── Sidebar.vue
    │   │   ├── Header.vue
    │   │   └── MainLayout.vue
    │   └── shared/
    │       ├── Loading.vue
    │       └── ErrorBoundary.vue
    ├── stores/
    │   ├── auth.ts            # Pinia auth store
    │   └── chat.ts            # Pinia chat store
    ├── router/
    │   └── index.ts           # Vue Router 配置 + 导航守卫
    ├── types/
    │   └── index.ts           # 对齐后端 Pydantic Schema
    └── utils/
        ├── markdown.ts
        └── audio.ts
```

## 与后端接口对照

| 前端页面 | 后端接口 |
|---------|---------|
| 登录 | `POST /api/v1/auth/login`（需后端新增） |
| 聊天 | `POST /api/v1/chat` + `POST /api/v1/chat/stream` |
| 会话列表 | `GET /api/v1/sessions` |
| 历史消息 | `GET /api/v1/session/{id}/messages` |
| 工单确认 | `POST /api/v1/ticket/confirm` |
| 语音 | `WS /api/v1/ws/chat/{session_id}` |
| 知识库管理 | `POST/GET/DELETE /api/v1/admin/knowledge/*` |
| 知识检索 | `POST /api/v1/knowledge/search` |
| Trace 查询 | `GET /api/v1/trace/{id}` + `/replay` |
| 成本仪表板 | `GET /api/v1/admin/cost` |
| 系统状态 | `GET /api/status` |

> **注意**：后端目前缺少 `POST /api/v1/auth/login` 接口（JWT 签发），R1 需要同步补充。
