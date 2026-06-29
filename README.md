# 🤖 Agent from Scratch

从零构建一个 AI Agent —— 手写 Agent Loop、Tool Use、Memory、MCP。

这是 **[DeepSeek Agent Harness 学习路线](https://github.com/gyk321/Agent-from-scratch)** 的配套项目，目标是通过动手实践，深入理解 AI Agent 的每一个底层机制。

## 项目结构

```
src/
├── agent.py      # 🔥 核心 Agent Loop（ReAct 模式）
├── tools.py      # 🔧 工具定义与执行（9 个工具）
└── main.py       # 💬 交互式对话入口
```

## 快速开始

### 1. 克隆 & 安装

```bash
git clone https://github.com/gyk321/Agent-from-scratch.git
cd Agent-from-scratch
python -m venv venv

# Windows
venv\Scripts\pip install -r requirements.txt

# macOS / Linux
venv/bin/pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
```

编辑 `.env`，填入你的 API Key：

```env
# DeepSeek（推荐）
DEEPSEEK_API_KEY=sk-xxx

# 或 Anthropic Claude
# ANTHROPIC_API_KEY=sk-ant-xxx
```

### 3. 运行 Demo

```bash
# Windows
$env:PYTHONIOENCODING = "utf-8"
venv\Scripts\python.exe -m src.agent

# macOS / Linux
python -m src.agent
```

Agent 会同时调用多个工具——查询时间并创建文件，展示 ReAct 循环的完整流程。

### 4. 交互模式

```bash
python -m src.main
```

```
You › 帮我查一下 DeepSeek 官网的最新公告，然后总结保存到 notes.txt

🔄 Iteration 1/10
  ⏱️  DeepSeek: 2.1s | in=1200 out=95 tokens
  💭 我来先获取官网内容...
  🔧 web_fetch("https://www.deepseek.com/")
  📋 DeepSeek | 探索未至之境 ...

🔄 Iteration 2/10
  ⏱️  DeepSeek: 1.8s | in=3400 out=120 tokens
  💭 已经获取了内容，现在总结并保存...
  🔧 write_file("notes.txt", "## DeepSeek 最新公告...")

Agent › 已完成！官网最新动态已总结到 notes.txt
```

## 学习路线

这个项目跟随一个四阶段螺旋式学习路线设计：

| Phase | 目标 | 关键产出 |
|-------|------|---------|
| **1. 深度沉浸** | 构建带工具调用的单 Agent | 个人 AI 助手 v1 |
| **2. 动手建造** | Multi-Agent + MCP + Skills | Mini Harness 开源项目 |
| **3. 原理深潜** | Transformer 内部、推理优化、安全沙箱 | 技术博客 + v2 重构 |
| **4. 开源贡献** | 向 LangChain / vLLM 等提 PR | 3-5 个 merged PR |

## 技术栈

- **LLM**：DeepSeek API / Anthropic Claude API
- **Tools**：文件操作、Shell 命令、网页抓取、SQLite 数据库
- **Memory**（Phase 1 W3）：ChromaDB 向量数据库
- **MCP**（Phase 2）：Model Context Protocol

## License

MIT
