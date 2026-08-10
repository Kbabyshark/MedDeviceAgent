# Prompt 模板目录

## 目录结构

```
prompts/
├── intent/           # 意图识别 Prompt
│   └── classify_v1.yaml
├── rag/              # RAG 回答 Prompt
│   ├── answer_v1.yaml
│   └── rewrite_v1.yaml
├── safety/           # 安全检测 Prompt
│   └── check_v1.yaml
├── summary/          # 摘要生成 Prompt
│   └── summarize_v1.yaml
├── tool/             # Tool 调用 Prompt
│   └── execute_v1.yaml
└── memory/           # Memory 提取 Prompt
    └── extract_v1.yaml
```

## Prompt 管理规范

- 所有 Prompt 在此统一管理，禁止代码中硬编码
- 每个 Prompt 文件包含版本号、模板内容、变量定义
- 支持 AB 测试：通过 `version` 字段区分
- Trace 记录时关联 Prompt 版本
