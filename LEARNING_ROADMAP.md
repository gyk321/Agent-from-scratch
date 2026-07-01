# 🤖 Agent from Scratch — 分层学习路线

> 从零构建 AI Agent，逐层深入每一个底层机制。
>
> **核心理念**：每层只依赖下一层，层内可替换。先跑通再理解，先理解再优化。

---

## 📚 六层架构总览

```
┌─────────────────────────────────────────────────────┐
│  Layer 6: 开源贡献                                    │
│  LangChain / vLLM / Chroma PR · 社区影响力             │
├─────────────────────────────────────────────────────┤
│  Layer 5: Multi-Agent 协作                           │
│  MCP 协议 · Agent 间通信 · 任务编排 · Skill 系统       │
├─────────────────────────────────────────────────────┤
│  Layer 4: 长期记忆 & RAG                              │
│  ChromaDB · Embedding · 语义检索 · 自动摘要            │
├─────────────────────────────────────────────────────┤
│  Layer 3: Agent 核心循环                              │
│  ReAct 模式 · Tool Use · Provider 抽象 · 对话管理      │
├─────────────────────────────────────────────────────┤
│  Layer 2: 工具系统                                    │
│  Tool Schema · 安全执行 · 错误处理 · 结果格式化         │
├─────────────────────────────────────────────────────┤
│  Layer 1: 基础设施                                    │
│  Python 3.10+ · API 调用 · 环境配置 · Git 工作流       │
└─────────────────────────────────────────────────────┘
```

> **学习方向**：从下往上（Layer 1 → 6）。每一层都以前一层为基础。
> **"为什么分层"**：新模型出来只需换 Layer 3 的 Provider、新存储出来只需换 Layer 4 的 DB——分层让你能局部升级而非全盘重写。

---

## Layer 1 · 基础设施

**目标**：把开发环境搭好，理解 LLM API 的基本调用模式。

| # | 知识点 | 状态 | 产出 |
|---|--------|------|------|
| 1.1 | Python 3.10+ 环境 & venv | ✅ | `venv/` |
| 1.2 | `.env` 环境变量管理 (python-dotenv) | ✅ | `.env` / `.env.example` |
| 1.3 | OpenAI SDK 调用 DeepSeek API | ✅ | `_call_deepseek()` |
| 1.4 | Anthropic SDK 调用 Claude API | ✅ | `_call_anthropic()` |
| 1.5 | Git 工作流 (commit / push / branch) | ✅ | GitHub 仓库 |
| 1.6 | `requirements.txt` 依赖管理 | ✅ | `requirements.txt` |

### 🔑 核心理解

```
用户代码 → HTTP Request → LLM API Server → Response → 用户解析
              ↑
         API Key 认证
```

**关键认知**：所有 LLM API 本质上是"发一段文本、收一段文本"。Tool Use、Streaming、JSON Mode 都只是这个基本模式的变体。DeepSeek 兼容 OpenAI 协议——同一套 SDK，换个 URL。

### 📖 延伸阅读
- [OpenAI API 文档](https://platform.openai.com/docs/api-reference)
- [DeepSeek API 文档](https://platform.deepseek.com/api-docs)

---

## Layer 2 · 工具系统

**目标**：让 LLM 能操作真实世界——文件、命令、网络、数据库。

| # | 知识点 | 状态 | 产出 |
|---|--------|------|------|
| 2.1 | Tool Schema 设计 (JSON Schema) | ✅ | `TOOL_DEFINITIONS` |
| 2.2 | 工具注册表模式 (name → function) | ✅ | `TOOL_MAP` |
| 2.3 | 文件操作工具 (读/写/列表) | ✅ | `read_file` / `write_file` / `list_files` |
| 2.4 | Shell 命令安全执行 (白名单) | ✅ | `shell_exec` |
| 2.5 | 网页抓取 (requests + BeautifulSoup) | ✅ | `web_fetch` |
| 2.6 | SQLite 数据库操作 (只读/写入分离) | ✅ | `db_query` / `db_exec` |
| 2.7 | 工具格式适配 (OpenAI ↔ Anthropic) | ✅ | `_to_openai_tools()` |
| 2.8 | 错误分层处理 (TypeError vs Exception) | ✅ | `_execute_tool` 三层防护 |

### 🔑 核心理解

```
LLM 看到的                    Python 执行的
─────────────                 ─────────────
TOOL_DEFINITIONS (声明)  →    TOOL_MAP (实现)
{
  "name": "web_fetch",        def web_fetch(url): ...
  "description": "...",       return requests.get(url).text
  "input_schema": {...}
}
```

**关键认知**：Tool Schema 是 LLM 和代码之间的**契约**。Schema 写得好不好，直接决定 LLM 能不能正确调用工具。描述要精确、参数要明确、required 字段要标清楚。

### 📖 延伸阅读
- [OpenAI Function Calling 指南](https://platform.openai.com/docs/guides/function-calling)
- [JSON Schema 规范](https://json-schema.org/)

---

## Layer 3 · Agent 核心循环

**目标**：实现 ReAct 模式——让 LLM 能"思考→行动→观察→再思考"。

| # | 知识点 | 状态 | 产出 |
|---|--------|------|------|
| 3.1 | ReAct 循环 (while + max_iterations) | ✅ | `agent.chat()` |
| 3.2 | System Prompt 设计 (Capability-First) | ✅ | `SYSTEM_PROMPT` |
| 3.3 | 对话历史管理 (messages 列表) | ✅ | `self.messages` |
| 3.4 | Provider 抽象 (DeepSeek / Anthropic) | ✅ | `_call_deepseek` / `_call_anthropic` |
| 3.5 | 响应解析标准化 (→ text + tool_calls) | ✅ | `_parse_*_response()` |
| 3.6 | 多工具并行调用 | ✅ | `for tc in tool_calls` |
| 3.7 | 可观测性 (stats / verbose / token 计数) | ✅ | `self.stats` |
| 3.8 | 交互式 REPL 界面 | ✅ | `main.py` (rich 库) |

### 🔑 核心理解

```
┌──────────────────────────────────────────────────┐
│                  ReAct Loop                        │
│                                                    │
│   用户输入 → [THINK] → [DECIDE] → 有工具？          │
│                  ↑                    ↓ 是          │
│                  └── [OBSERVE] ←── [ACT]           │
│                               ↓ 否                  │
│                          返回最终回答               │
│                                                    │
│   安全阀：max_iterations = 10                      │
└──────────────────────────────────────────────────┘
```

**关键认知**：Agent 的"智能"不来自模型本身，而来自**循环结构**。模型只负责单步推理，Agent 负责把多步推理串起来。这意味着：更好的模型让每一步更准，更好的循环让任务能完成更复杂的任务。两者正交。

### 📖 延伸阅读
- [ReAct 论文](https://arxiv.org/abs/2210.03629)
- [Anthropic Tool Use 文档](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)

---

## Layer 4 · 长期记忆 & RAG

**目标**：让 Agent 拥有跨会话记忆，能"记住"用户之前说过的话。

| # | 知识点 | 状态 | 产出 |
|---|--------|------|------|
| 4.1 | 向量数据库概念 (Embedding + 相似度搜索) | ✅ | `memory.py` |
| 4.2 | ChromaDB PersistentClient (数据持久化) | ✅ | `MemoryManager.__init__` |
| 4.3 | 记忆存储 (text → vector → disk) | ✅ | `remember()` |
| 4.4 | 语义检索 (query → vector → top-K) | ✅ | `recall()` |
| 4.5 | 自动摘要策略 (关键词匹配 → LLM 驱动) | ✅ | `summarize_and_remember()` |
| 4.6 | 记忆注入 System Prompt | ✅ | `_build_system_prompt()` |
| 4.7 | 单例模式 (全局唯一 MemoryManager) | ✅ | `get_memory()` |
| 4.8 | 记忆工具暴露给 Agent (remember / recall) | ✅ | `remember_info` / `recall_info` |

### 🔑 核心理解

```
写入路径                         读取路径
────────                         ────────
"用户叫小明"                       "猫叫什么？"
    ↓                                ↓
Embedding 模型                   Embedding 模型
    ↓                                ↓
[0.12, -0.34, ...]              [0.08, -0.41, ...]
    ↓                                ↓
ChromaDB 存储 ──── 持久化 ────→ 向量相似度搜索
                                     ↓
                              "小明的猫叫橘子" (dist=0.26)
                                     ↓
                              注入 System Prompt
```

**关键认知**：RAG (Retrieval-Augmented Generation) = 先检索相关内容，再让 LLM 基于内容生成回答。记忆系统本质上就是一个**个人 RAG 系统**——知识库是你的对话历史。

**Embedding 模型选型**：
| 方案 | 优点 | 缺点 |
|------|------|------|
| ChromaDB ONNX (当前) | 本地运行、零费用 | 中文效果一般 |
| sentence-transformers | 模型选择多 | 需要 PyTorch (几 GB) |
| DeepSeek Embedding API | 效果好、免部署 | 需要网络、有费用 |

### 📖 延伸阅读
- [ChromaDB 文档](https://docs.trychroma.com/)
- [RAG 原理](https://www.pinecone.io/learn/retrieval-augmented-generation/)
- [all-MiniLM-L6-v2 模型卡](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

---

## Layer 5 · Multi-Agent 协作 & MCP

**目标**：多个 Agent 分工协作，通过标准协议通信，动态加载技能。

| # | 知识点 | 状态 | 产出 |
|---|--------|------|------|
| 5.1 | MCP 协议 (Model Context Protocol) | 🔲 | `mcp_server.py` |
| 5.2 | Agent 间通信 (消息路由) | 🔲 | `orchestrator.py` |
| 5.3 | 任务编排 (DAG / Pipeline) | 🔲 | — |
| 5.4 | Skill 系统 (动态加载 & 热插拔) | 🔲 | `skills/` |
| 5.5 | 角色分工 (Planner / Executor / Reviewer) | 🔲 | — |
| 5.6 | 上下文窗口管理 (压缩 / 摘要) | 🔲 | — |
| 5.7 | 错误恢复 & 重试策略 | 🔲 | — |
| 5.8 | 性能监控 (延迟 / Token / 成本) | 🔲 | — |

### 🔑 核心理解

```
                     ┌──────────────┐
                     │  Orchestrator │  ← 任务分发
                     └──┬───┬───┬──┘
                        │   │   │
              ┌─────────┘   │   └─────────┐
              ↓             ↓             ↓
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Researcher│ │  Coder   │ │ Reviewer │  ← 专业 Agent
        │ (搜索+阅读)│ │ (写代码)  │ │ (审查+测试)│
        └──────────┘ └──────────┘ └──────────┘
              │             │             │
              └─────────────┼─────────────┘
                            ↓
                    ┌──────────────┐
                    │  MCP Server  │  ← 统一工具协议
                    │  (filesystem) │
                    │  (web_search) │
                    │  (database)   │
                    └──────────────┘
```

**关键认知**：单 Agent 靠"循环"变聪明，多 Agent 靠"分工"变强大。就像一个人 vs 一个团队——不是模型更强了，而是组织结构让复杂任务可以被拆解。

**MCP (Model Context Protocol)**：Anthropic 提出的开放协议，让 Agent 和工具之间用标准方式通信。类比：USB 标准——不管什么设备，插上就能用。

### 📖 延伸阅读
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Anthropic MCP 介绍](https://www.anthropic.com/news/model-context-protocol)

---

## Layer 6 · 开源贡献

**目标**：把学到的东西回馈社区，建立技术影响力。

| # | 方向 | 状态 | 目标项目 |
|---|------|------|---------|
| 6.1 | 修 Bug (good first issue) | 🔲 | LangChain / vLLM |
| 6.2 | 写文档 & 教程 | 🔲 | — |
| 6.3 | 提 Feature (小功能) | 🔲 | Chroma / LiteLLM |
| 6.4 | 写技术博客 (分享学习过程) | 🔲 | 个人博客 / 知乎 |
| 6.5 | 开源自己的 Agent Harness | 🔲 | Agent-from-scratch |

### 🔑 核心认知

**开源的复利效应**：修一个 Bug → 被 maintainer 认识 → 下一个 PR 更容易 merge → 积累声誉 → 更好的工作机会 / 合作邀请。Phase 1-3 的积累就是你贡献的底气。

---

## 📊 当前进度仪表盘

```
Layer 1 ████████████████████ 100%  基础设施 OK
Layer 2 ████████████████████ 100%  11 个工具就绪
Layer 3 ████████████████████ 100%  ReAct 循环 + 交互界面
Layer 4 ████████████████████ 100%  ChromaDB 记忆系统
Layer 5 ░░░░░░░░░░░░░░░░░░░░   0%  🚀 下一站
Layer 6 ░░░░░░░░░░░░░░░░░░░░   0%  等待 Phase 1-3 积累
```

### 📈 累计产出

| 指标 | 数字 |
|------|------|
| 代码文件 | 5 个 (`agent.py`, `tools.py`, `memory.py`, `main.py`, `__init__.py`) |
| 总代码行数 | ~750 行 |
| 工具数量 | 11 个 |
| 支持 Provider | 2 个 (DeepSeek + Anthropic) |
| 记忆条目 | ChromaDB 持久化 |
| Git Commits | 1 (待提交 Week 3 变更) |

---

## 🗺️ 推荐学习节奏

### 每个 Layer 的标准流程

```
1. 阅读文档 (30min)  →  了解概念
2. 代码精读 (30min)  →  理解实现
3. 动手修改 (30min)  →  改一个参数/加一个功能，看效果
4. 写笔记 (15min)    →  用自己的话总结
```

### 时间线建议

| 阶段 | 内容 | 预计时间 |
|------|------|---------|
| **已完成** | Layer 1-4 (基础设施→记忆系统) | ~2 周 |
| **当前** | Layer 5 MCP 协议学习 | 1 周 |
| **下一步** | Layer 5 Multi-Agent 实现 | 2-3 周 |
| **进阶** | Layer 5 Skill 系统 | 1-2 周 |
| **深潜** | Layer 3+4 重构 + 测试 | 1 周 |
| **输出** | Layer 6 开源贡献 | 持续 |

---

## 📁 仓库文件索引

```
Agent-from-scratch/
├── LEARNING_ROADMAP.md    ← 📍 你在这里 (学习路线)
├── README.md              ← 项目介绍 & 快速开始
├── code-review-agent.md   ← agent.py 逐行精读笔记
├── requirements.txt       ← 依赖清单
├── .env.example           ← 环境变量模板
│
└── src/
    ├── __init__.py        ← 包说明
    ├── agent.py           ← Layer 3: Agent 核心循环
    ├── tools.py           ← Layer 2: 工具定义 & 执行
    ├── memory.py          ← Layer 4: 长期记忆系统
    └── main.py            ← Layer 3: 交互式界面入口
```

---

## 🎯 阶段性检查点

每完成一个 Layer，问自己三个问题：

1. **数据流**：输入是什么 → 经过了什么处理 → 输出是什么？能画出来吗？
2. **边界条件**：输入为空会怎样？超时会怎样？API 挂了会怎样？
3. **怎么替换**：如果不用 ChromaDB 改用 Pinecone，要改哪几个地方？

三个都能回答 → 这一层真正吃透了。

---

> 📅 最后更新：2026-07-02 | ✍️ 作者：gyk321
>
> ⭐ 如果这个学习路线对你有帮助，欢迎 Star：[Agent-from-scratch](https://github.com/gyk321/Agent-from-scratch)
