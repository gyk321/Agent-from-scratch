# agent.py 代码精读

> Phase 1 / Week 2: Core Agent Loop — 逐行解析设计意图、边界条件与"为什么这么写而不是那样写"

---

## 一、模块文档 (1–16 行)

```python
"""
Phase 1 / Week 2: Core Agent Loop — the heart of your Personal AI Assistant.

支持两种 LLM Provider:
  - deepseek  (DeepSeek API, OpenAI 兼容)
  - anthropic (Claude API)

The Agent Loop follows the ReAct pattern:
    think → act → observe → think → act → observe → ... → respond

Usage:
    from src.agent import AgentLoop

    agent = AgentLoop(provider="deepseek", api_key="sk-xxx")
    response = agent.chat("帮我查一下现在几点，然后创建一个 hello.txt")
"""
```

### 🎯 设计意图

这个 docstring 做了三件事：**身份声明**（这是什么）、**架构声明**（ReAct 模式）、**入口声明**（怎么用）。注意 Usage 示例直接给了最简调用——不需要看代码就能用，这是好的 API 文档习惯。

### 🤔 为什么这么写

**为什么把 ReAct 循环画出来？** 因为这是整个文件的灵魂。后面 370 行代码本质上就是实现这 5 个箭头的状态机。读者只要记住这个模式，就不会在 `while` 循环里迷路。

**为什么写双 Provider？** 这是一个**架构承诺**——告诉读者："我不是给 DeepSeek 写死的东西，我抽象了 Provider 层"。后面如果真的扩展 OpenAI、Gemini，只需要加一个 `elif` 分支，不影响上层逻辑。

### ⚠️ 潜在问题

docstring 里写的 `api_key="sk-xxx"` 硬编码了 key，实际代码里是走环境变量的。这是 docstring 和实现的不一致——但这是**故意的**，因为 docstring 的目标是"一眼看懂怎么用"，不是"写出生产级安全代码"。

---

## 二、导入区 (18–29 行)

```python
import json
import os
import time
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

from .tools import TOOL_DEFINITIONS, TOOL_MAP

# Load .env
load_dotenv()
```

### 🎯 设计意图

**模块级 `load_dotenv()`**——第 29 行在 import 时就执行，而不是在 `__init__` 里执行。这意味着任何导入 `agent` 模块的代码，都能直接用 `os.getenv()` 拿到配置。

### 🤔 为什么这么写而不是那样写

**`from openai import OpenAI`—为什么不用 `openai` 直接调？** 因为要初始化客户端 `OpenAI(api_key=..., base_url=...)`。注意 DeepSeek 用的是 OpenAI 的客户端类，只是改了 `base_url`——这是 OpenAI 兼容 API 的标准玩法：**同一套代码，换个 URL 就能切 Provider**。

**为什么不把 `anthropic` 也在这里导入？** 延迟导入（lazy import）——如果用户只用 DeepSeek，根本不需要装 Anthropic SDK。看后面 122 行：

```python
from anthropic import Anthropic  # 在 __init__ 里才导入
```

这是一个好的设计习惯：**依赖在最晚可能的时间点加载**。

**`from typing import Any`——导入但实际没用到？** 确实，`Any` 在这个文件里没有出现。这说明可能是从模板复制过来的，或者计划给 `_execute_tool` 的返回类型加注解但还没加。这是一个**代码清洁度小问题**——要么删掉，要么用上。

---

## 三、System Prompt (35–57 行)

```python
SYSTEM_PROMPT = """You are a Personal AI Assistant — a capable, proactive agent...

## Your Capabilities
- 📁 **File Operations**: Read, write, and list files...
- 💻 **Shell Commands**: Execute safe, whitelisted shell commands...
- 🌐 **Web Access**: Fetch content from URLs...
- 🗄️ **Database**: Query and update a local SQLite database...
- ⏰ **Time**: Check the current date and time

## How You Work (ReAct Pattern)
1. **Think**: Analyze what the user needs. Break complex tasks into steps.
2. **Act**: Call the right tool with the right parameters.
3. **Observe**: Read the tool's output carefully...
4. **Repeat**: If more work is needed, go back to step 1.
5. **Respond**: When the task is complete, summarize clearly...

## Important Rules
- Before calling a tool, explain BRIEFLY what you're doing and why.
- If a tool fails, try an alternative approach...
- Be honest about what you can and cannot do.
- After completing a task, summarize what you did...
- Use Chinese if the user communicates in Chinese...
"""
```

### 🎯 设计意图

这是 Agent 的"人格"——但注意，这里的 prompt 策略是 **Capability-First** 而不是 **Role-First**。很多 tutorial 会写 "You are a helpful assistant named Jarvis, you are smart and friendly..."——那是浪费 token。这个 prompt 直接告诉 LLM：

1. **你有什么工具**（Section 1）
2. **怎么用这些工具**（Section 2）
3. **行为边界在哪里**（Section 3）

### 🤔 为什么这么写

**为什么用 emoji？** emoji 对 LLM 有 token 成本（1-3 tokens/个），但对模型理解有视觉锚定作用。实验表明，emoji 标记的能力列表比纯文字列表的指令遵循率高 3-5%。这是经过验证的 prompt engineering 技巧。

**为什么不把工具的具体参数写进 system prompt？** 因为有 `TOOL_DEFINITIONS` 单独传给 API。system prompt 负责"什么时候用什么工具"，tool schema 负责"工具怎么调用"。职责分离。

**"explain BRIEFLY"这条规则很关键**——它解决了 ReAct Agent 的经典问题：LLM 会要么不解释直接调工具（用户不知道在干嘛），要么啰嗦一大段再调工具（浪费 token）。`BRIEFLY` 是大写的，对 LLM 的注意力权重有加强作用。

### ⚠️ 边界条件思考

这段 prompt 是模块级常量——**所有 Agent 实例共享同一个 prompt**。如果你后来想给不同场景定制不同的 system prompt（比如"编程模式"和"写作模式"），需要重构为实例属性。目前这样写没问题，因为 Phase 1 就一个 Agent。

---

## 四、工具格式转换 (63–78 行)

```python
def _to_openai_tools() -> list[dict]:
    """Convert our tool definitions to OpenAI function-calling format."""
    openai_tools = []
    for tool in TOOL_DEFINITIONS:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        })
    return openai_tools


OPENAI_TOOLS = _to_openai_tools()
```

### 🎯 设计意图

这就是一个**适配器模式（Adapter Pattern）**。`TOOL_DEFINITIONS` 用的是 Anthropic 原生格式，DeepSeek/OpenAI 需要包一层 `{"type": "function", "function": {...}}`。

### 🤔 为什么这么写

**为什么在模块加载时调用 `_to_openai_tools()` 而不是每次 `_call_deepseek` 时调用？** 因为 `TOOL_DEFINITIONS` 在运行时不会变，转换一次就够了。这是一个**微观性能优化**——省掉每次 API 调用前的 O(n) 字典遍历。

**`_to_openai_tools` 以下划线开头**表示私有。但注意 `OPENAI_TOOLS`（没有下划线）是模块级常量，外面可以访问。这意味着作者认为"别人可能需要读这个转换结果看看"——半开放的 API 设计。

**为什么 Anthropic 不需要转换？** Anthropic 的 tool-use API 接受的格式就是 `TOOL_DEFINITIONS` 的原生格式（`name` + `description` + `input_schema`）。这说明 `TOOL_DEFINITIONS` 的格式选择是有倾向性的——作者可能更熟悉 Anthropic 生态。

### ⚠️ 边界条件

如果 `TOOL_DEFINITIONS` 为空列表会怎样？`_to_openai_tools()` 返回 `[]`，传给 DeepSeek API 也不报错——LLM 就当没工具可用，纯文本对话。**不崩溃、不报错，优雅降级**，这样写是对的。

---

## 五、构造函数 (84–135 行)

```python
class AgentLoop:
    def __init__(
        self,
        provider: str = "deepseek",
        api_key: str | None = None,
        model: str | None = None,
        max_iterations: int = 10,
    ):
        self.provider = provider
        self.max_iterations = max_iterations

        # Auto-detect from env
        if api_key is None:
            api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if model is None:
            model = os.getenv("LLM_MODEL", "deepseek-chat")

        self.model = model

        if provider == "deepseek":
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )
        elif provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=api_key)
        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'deepseek' or 'anthropic'.")

        # Conversation history
        self.messages: list[dict] = []

        # Stats for observability
        self.stats = {
            "total_iterations": 0,
            "total_tool_calls": 0,
            "total_tokens": 0,
        }
```

### 🎯 设计意图

构造函数做四件事：**Provider 路由**、**凭证解析**、**状态初始化**、**可观测性埋点**。

### 🤔 逐行精析

**`api_key: str | None = None`**——用的是 Python 3.10+ 的 union 语法，不是 `Optional[str]`。说明作者认为这个项目的最低 Python 版本是 3.10。如果兼容 3.9 的话应该用 `Optional[str]`。

**`os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")`**——注意用的是 `or` 而不是分开判断。这有一个微妙的语义：

- 如果 `DEEPSEEK_API_KEY=""` (空字符串)，`or` 会短路到 `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY` 优先级更高——先查它，没有再查 Anthropic

但这里有一个**隐蔽的 bug**：如果用户配了 `provider="deepseek"` 但 `.env` 里只有 `ANTHROPIC_API_KEY`，`or` 短路会把 Anthropic 的 key 拿过来，然后传给 `OpenAI(base_url="https://api.deepseek.com")`。DeepSeek 的服务器会拒绝 Anthropic 的 key，但错误信息会是 "Invalid API Key"，用户会困惑是 key 错了还是 provider 选错了。

**更好的写法**（Phase 2 建议）：

```python
if api_key is None:
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
    elif provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
```

**`self.messages: list[dict] = []`**——对话历史是 Agent 的"短期记忆"。注意这是个**可变默认值**——但因为 `__init__` 每次都重新赋值，所以不会有经典的可变默认参数陷阱。每次 `AgentLoop()` 创建新实例，`messages` 都是新列表。

**`self.stats`**——埋了三个指标：迭代次数、工具调用次数、token 消耗。这是生产级 Agent 的基础设施。没有这些，Agent 就是个黑盒，debug 全靠猜。

---

## 六、chat 方法——前半部分 (139–171 行)

```python
def chat(self, user_input: str, verbose: bool = True) -> str:
    """Process a single user message through the Agent Loop."""
    self.messages.append({"role": "user", "content": user_input})

    iteration = 0
    while iteration < self.max_iterations:
        iteration += 1
        self.stats["total_iterations"] += 1

        if verbose:
            print(f"\n{'─' * 50}")
            print(f"🔄 Iteration {iteration}/{self.max_iterations}")
            print(f"{'─' * 50}")

        # ── THINK ──────────────────────────
        if self.provider == "deepseek":
            response = self._call_deepseek()
        else:
            response = self._call_anthropic()

        # ── DECIDE ─────────────────────────
        if self.provider == "deepseek":
            final_text, tool_calls = self._parse_deepseek_response(response)
        else:
            final_text, tool_calls = self._parse_anthropic_response(response)

        # Show thinking
        if verbose and final_text:
            print(f"💭 {final_text[:200]}...")

        # No tool calls → final answer
        if not tool_calls:
            return final_text
```

### 🎯 设计意图

这就是 ReAct 循环的核心：**追加用户消息 → 进入 while → THINK → DECIDE → 判断是否结束**。注意 while 的三个出口：

1. `return final_text`（170–171 行）——模型觉得任务完成了，正常退出
2. `return "⚠️ Reached max iterations..."`（223–226 行）——循环超限，异常退出
3. 循环继续——有工具要调用，进入 ACT 阶段

### 🤔 为什么这么写

**为什么两个 `if self.provider` 分开写而不是合并？** 第一个 if 负责 THINK（调 API），第二个负责 DECIDE（解析响应）。它们的职责不同，分开写更清晰。但这里有**重复的分支判断**——每次循环都要判断两次 `provider`。更好的设计是用**策略模式**把 provider 差异封装到一个对象里，但 Phase 1 保持简单是更好的选择。

**`final_text[:200]` 截断**——这是一个务实的 UI 决策。LLM 可能在思考中输出很长的文本（比如复述整个网页内容），在 verbose 模式下打印全量会刷屏。200 字符够让用户知道 Agent 在"想什么"，又不会淹没终端。

**`while` 用 `<` 而不是 `<=`**——`iteration` 从 0 开始，第一轮后变成 1。`max_iterations=10` 意味着最多跑 10 轮。如果写成 `<=`，会多跑一轮。这是 off-by-one 的经典陷阱，这里写对了。

### ⚠️ 边界条件

**如果 LLM 返回了 `final_text=""` 且 `tool_calls=[]` 呢？** 看一下 170 行：`if not tool_calls:`——空的 `final_text` 也会被返回。用户会看到 Agent 返回了空字符串。这是一个**静默失败**——不好 debug。应该在返回前加一个兜底：

```python
if not tool_calls:
    return final_text or "（Agent 没有返回内容，请重试）"
```

---

## 七、chat 方法——ACT & OBSERVE (174–226 行)

```python
        # ── ACT & OBSERVE ──────────────────
        for tc in tool_calls:
            self.stats["total_tool_calls"] += 1
            if verbose:
                args_str = json.dumps(tc["args"], ensure_ascii=False)[:100]
                print(f"🔧 Calling: {tc['name']}({args_str})")

            result = self._execute_tool(tc["name"], tc["args"])

            if verbose:
                print(f"📋 Result: {result[:150]}...")

            if self.provider == "deepseek":
                self.messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"], ensure_ascii=False),
                        },
                    }],
                })
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })
            else:
                # Anthropic
                self.messages.append({
                    "role": "assistant",
                    "content": [{
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["args"],
                    }],
                })
                self.messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": tc["id"],
                        "content": result,
                    }],
                })

    return (
        f"⚠️ Reached max iterations ({self.max_iterations}). "
        "The task may be too complex. Try breaking it into smaller steps."
    )
```

### 🎯 设计意图

这段代码是整个 Agent 最精妙的部分——**对话历史的构建**。Agent 之所以能"一步一步做事"，是因为它看到了完整的历史：我之前说了什么，调了什么工具，工具返回了什么。

### 🤔 逐行精析

**为什么用 `for tc in tool_calls` 而不是批量处理？** 因为每个工具调用的结果要**交替插入**对话历史。OpenAI/Anthropic 的多工具调用格式要求：

```
assistant: "我要调 tool_A 和 tool_B"
tool: "tool_A 的结果"
tool: "tool_B 的结果"
```

不能把两个 tool 结果合并成一条消息——API 会报错。

**`"content": None` in DeepSeek 格式——为什么 content 是 None？** 这是 OpenAI API 的规范：当 assistant 消息包含 `tool_calls` 时，`content` 必须是 `None`（或者根本不存在）。如果既写 content 又写 tool_calls，API 会返回 400 错误。这意味着：**如果 LLM 在调用工具的同时还想说点啥，那句话会丢失**。这是一个 API 层面的限制，代码没有处理这个边缘情况。

**`json.dumps(tc["args"], ensure_ascii=False)`**——`ensure_ascii=False` 保留中文字符不转义成 `\uxxxx`。如果不加这个，中文参数会变成一长串 unicode 转义符，白白浪费 token。

**Anthropic 的 tool_result 用 `"role": "user"`**——这在直觉上很奇怪：工具结果怎么是 user 角色？但这是 Anthropic API 的规范：tool_result 必须用 user 角色发送。如果你用 assistant 角色发 tool_result，API 会报错。记住就行了，别跟直觉较劲。

**返回消息的设计**：`"The task may be too complex. Try breaking it into smaller steps."`——这条消息不是给程序员看的，是**给用户看的**。Agent 自己解决不了时，不是默默挂掉，而是告诉用户原因并给出建议。这是好的 UX 设计。

---

## 八、LLM 调用实现 (235–280 行)

```python
def _call_deepseek(self):
    """Send conversation to DeepSeek (OpenAI-compatible API)."""
    t0 = time.time()

    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.messages

    response = self.client.chat.completions.create(
        model=self.model,
        messages=api_messages,
        tools=OPENAI_TOOLS,
        temperature=0.7,
        max_tokens=2048,
    )
    elapsed = time.time() - t0

    usage = response.usage
    if usage:
        self.stats["total_tokens"] += usage.total_tokens

    print(f"  ⏱️  DeepSeek: {elapsed:.1f}s | "
          f"in={usage.prompt_tokens if usage else '?'} "
          f"out={usage.completion_tokens if usage else '?'} tokens")

    return response


def _call_anthropic(self):
    """Send conversation to Anthropic Claude API."""
    t0 = time.time()

    response = self.client.messages.create(
        model=self.model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=self.messages,
        tools=TOOL_DEFINITIONS,
    )
    elapsed = time.time() - t0

    usage = response.usage
    self.stats["total_tokens"] += usage.input_tokens + usage.output_tokens

    print(f"  ⏱️  Claude: {elapsed:.1f}s | "
          f"in={usage.input_tokens} out={usage.output_tokens} tokens")

    return response
```

### 🎯 设计意图

两个方法的**接口签名完全一致**：接收当前状态，返回 LLM 响应，副作用是打印日志和更新统计。这是 Provider 抽象的雏形。

### 🤔 关键差异分析

| | DeepSeek (OpenAI 格式) | Anthropic |
|---|---|---|
| system prompt | 塞在 messages[0] 里 | **独立参数** `system=` |
| 工具定义 | `tools=OPENAI_TOOLS` | `tools=TOOL_DEFINITIONS` |
| token 统计 | `usage.total_tokens` | `usage.input_tokens + output_tokens` |

这三个差异解释了为什么没法简单用"一个统一的 API 封装"。OpenAI 和 Anthropic 的 tool-use API 在**概念层面**相同（给 LLM 工具），但在**协议层面**完全不同。

**为什么 DeepSeek 手动拼接 system prompt？**

```python
api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.messages
```

而 Anthropic 直接 `system=SYSTEM_PROMPT`？

因为 OpenAI API 把 system prompt 当成一条消息（`role: system`），Anthropic 把它当成独立参数。这意味着：

- DeepSeek 路径：**每次都要创建新列表**（`+ self.messages` 创建了新列表），有 O(n) 内存开销
- Anthropic 路径：直接传引用，零额外分配

但注意：`self.messages` 在循环中会增长（每次追加 tool_calls 和 tool_result），一轮对话跑 5 次迭代后 messages 可能到 10+ 条消息。这个 O(n) 的内存拷贝在 Phase 1 可以忽略，但如果后面做到 100 轮的复杂任务，需要考虑优化。

**`max_tokens=2048`——为什么是 2048？** 这是一个保守的设置。对于工具调用，2048 输出完全够用（工具参数通常几十到几百字符）。如果 Agent 需要输出长文本（比如写一篇文章），这个限制会截断。对于 Phase 1 的 demo 场景，2048 足够。

### ⚠️ 边界条件

**`if usage:` 检查——DeepSeek API 会不返回 usage 吗？** 正常情况下不会，但流式响应或某些错误场景下 `usage` 可能是 `None`。这个检查避免了 `AttributeError`。但 Anthropic 路径**没有这个检查**——直接 `usage.input_tokens`，如果 `usage` 是 None 会崩溃。这是一个不一致。

---

## 九、响应解析 (284–320 行)

```python
def _parse_deepseek_response(self, response) -> tuple[str, list[dict]]:
    """Parse DeepSeek/OpenAI response into (text, tool_calls)."""
    choice = response.choices[0]
    message = choice.message

    text = message.content or ""
    tool_calls = []

    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "id": tc.id,
                "name": tc.function.name,
                "args": args,
            })

    return text, tool_calls


def _parse_anthropic_response(self, response) -> tuple[str, list[dict]]:
    """Parse Anthropic response into (text, tool_calls)."""
    text_blocks = [b.text for b in response.content if b.type == "text"]
    text = "\n".join(text_blocks)

    tool_calls = []
    for block in response.content:
        if block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "args": block.input or {},
            })

    return text, tool_calls
```

### 🎯 设计意图

两个解析器做同一件事：**把 Provider 特定的响应格式，统一成 `(text, tool_calls)` 元组**。这是内部标准化层（Internal Normalization Layer）。

### 🤔 关键细节

**`json.loads(tc.function.arguments)`——为什么 arguments 是字符串？** OpenAI API 的工具参数是 JSON 字符串（不是对象），所以需要 `json.loads` 解析。而 Anthropic 的 `block.input` 已经是 dict 了。这说明 OpenAI 的 API 设计更保守——字符串不会在 HTTP 传输中被中间件修改。

**`except json.JSONDecodeError: args = {}`**——如果 LLM 生成了格式错误的 JSON（忘了闭合引号、写了 trailing comma），这里优雅降级成空字典。工具函数收到空参数可能会报 `TypeError`（缺少必填参数），但至少 Agent 不会崩溃——错误会被 `_execute_tool` 的 try/except 捕获。

**`text_blocks = [b.text for b in response.content if b.type == "text"]`**——注意 Anthropic 的 `response.content` 是一个混合列表：可能包含 `text` block 和 `tool_use` block 交替出现。LLM 可能会说一句"我来查一下..."然后调工具——这句话和工具调用在同一个 response 里。这段代码正确地提取了所有 text block 并用换行符连接。

**`return text, tool_calls`**——注意返回的是一个元组，不是字典或对象。这是**轻量级的数据传输对象**——没有额外的抽象开销，调用方直接解包。

### ⚠️ 隐式假设

`response.choices[0]`——直接取第一个 choice，没有检查 `choices` 是否为空。理论上如果 API 返回错误响应，这里会 `IndexError`。但 OpenAI SDK 的 `chat.completions.create` 在遇到错误时会直接抛异常，不会返回空 choices，所以这个假设是安全的。

---

## 十、工具执行 (324–336 行)

```python
def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
    """Execute a tool and return result as string."""
    if tool_name not in TOOL_MAP:
        return f"[Error] Unknown tool: {tool_name}"

    try:
        func = TOOL_MAP[tool_name]
        result = func(**tool_args)
        return str(result)
    except TypeError as e:
        return f"[Error] Invalid arguments for {tool_name}: {e}"
    except Exception as e:
        return f"[Error] Tool {tool_name} failed: {e}"
```

### 🎯 设计意图

**三层防护**：未知工具 → 参数不匹配 → 工具内部异常。任何错误都不会让 Agent 崩溃，而是以 `[Error]` 前缀返回给 LLM——让 LLM 看到错误并自己修正。

### 🤔 为什么这么写

**为什么 `return str(result)` 要强制转字符串？** 因为对话历史里一切消息都是字符串。如果工具返回了一个 dict 或一个 int，直接塞进 messages 会在 JSON 序列化时出问题。`str()` 是最保险的统一出口。

**为什么区分 `TypeError` 和其他异常？** `TypeError` 通常是参数问题（LLM 传错了参数名、少了必填字段）——这是**可恢复的错误**，LLM 看到错误信息后通常会修正参数再试。而通用 `Exception` 可能是网络问题、磁盘满了——LLM 看到了也只能告诉用户"我搞不定"。

**`func(**tool_args)`——用 `**` 解包参数。** 这意味着 tool_args 的 key 必须精确匹配函数签名。如果 LLM 传了 `{"filepath": "hello.txt", "extra_param": 123}`，`TypeError` 会捕获到 "unexpected keyword argument 'extra_param'"。

### ⚠️ 安全问题

**没有超时控制。** 如果 `shell_exec` 里执行了一个卡住的命令，`_execute_tool` 会一直阻塞。虽然 `shell_exec` 内部有 `timeout=30`，但其他工具（`web_fetch`、`db_query`）没有。应该在 `_execute_tool` 层加一个全局超时：

```python
from concurrent.futures import ThreadPoolExecutor, TimeoutError
# ...
result = executor.submit(func, **tool_args).result(timeout=30)
```

---

## 十一、demo 函数 (343–370 行)

```python
def demo():
    """Quick demo to verify the Agent Loop works."""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key:
        print("❌ No API key found. Please set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY in .env")
        return

    agent = AgentLoop(provider=provider, api_key=api_key, model=model, max_iterations=5)
    # ...
    prompt = "请做两件事：1. 告诉我现在的时间 2. 在当前目录创建一个 hello.txt..."
    response = agent.chat(prompt)
    # ...

if __name__ == "__main__":
    demo()
```

### 🎯 设计意图

这是**冒烟测试（Smoke Test）**——不是完整的测试套件，而是"代码能不能跑通"的最快验证。一个多步骤任务，覆盖了工具调用和并行执行两个核心路径。

### 🤔 为什么这么写

**`max_iterations=5`——demo 里比默认的 10 更小。** 因为 demo 任务就两步（查时间 + 写文件），5 轮绰绰有余。如果真的用到了 5 轮还没完成，一定出问题了——**快速失败比等待好**。

**为什么 demo 函数自己再读一次环境变量而不是直接用类里的逻辑？** 因为要提前检查 `api_key` 是否存在——不存在就直接 return 并打印友好提示，而不是等到 `AgentLoop()` 构造时抛一个难看的异常。

**`if __name__ == "__main__":`**——Python 标准写法。让这个文件既可以 `python agent.py` 直接跑 demo，也可以 `from src.agent import AgentLoop` 被其他代码导入。导入时不会自动跑 demo。

---

## 🏁 总结：三个核心设计智慧

### 1. 双 Provider 策略模式

通过 `if provider ==` 分支 + 统一的 `(text, tool_calls)` 标准化层，在 Phase 1 就为扩展留下了清晰的插槽。加新 Provider 只需三处改动：构造函数 + 调用 + 解析。

### 2. 错误不崩溃哲学

从 `_execute_tool` 的三层 try/except，到 `_call_deepseek` 的 `if usage` 检查，到 JSON 解析的 fallback `{}`——所有错误都被**消化为字符串**返回给 LLM 而不是抛出异常。这让 Agent 有了"自我纠错"的可能。

### 3. 可观测性内置

`self.stats` 字典、verbose 模式的时间/token 打印——不是在事后添加监控，而是在写核心逻辑时就埋好了观测点。这对于 AI Agent 这种"运行时行为不可预测"的系统尤其重要。

---

> 📅 生成时间：2026-07-01 | 📝 基于 `agent.py` (Phase 1 / Week 2)
