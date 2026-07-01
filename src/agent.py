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

import json
import os
import time
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

from .tools import TOOL_DEFINITIONS, TOOL_MAP
from .memory import get_memory

# Load .env
load_dotenv()

# ──────────────────────────────────────────────
# System Prompt
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Personal AI Assistant — a capable, proactive agent that helps your user with daily tasks.

## Your Capabilities
- 📁 **File Operations**: Read, write, and list files on the user's computer
- 💻 **Shell Commands**: Execute safe, whitelisted shell commands
- 🌐 **Web Access**: Fetch content from URLs to research and gather information
- 🗄️ **Database**: Query and update a local SQLite database for persistent storage
- ⏰ **Time**: Check the current date and time

## How You Work (ReAct Pattern)
1. **Think**: Analyze what the user needs. Break complex tasks into steps.
2. **Act**: Call the right tool with the right parameters.
3. **Observe**: Read the tool's output carefully. Did it succeed? What did you learn?
4. **Repeat**: If more work is needed, go back to step 1.
5. **Respond**: When the task is complete, summarize clearly for the user.

## Important Rules
- Before calling a tool, explain BRIEFLY what you're doing and why.
- If a tool fails, try an alternative approach or ask the user for guidance.
- Be honest about what you can and cannot do.
- After completing a task, summarize what you did and any important findings.
- Use Chinese if the user communicates in Chinese. Use English if they use English.
"""

# ──────────────────────────────────────────────
# Tool format conversion: our format → OpenAI format
# ──────────────────────────────────────────────

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

# ──────────────────────────────────────────────
# Agent Loop Implementation
# ──────────────────────────────────────────────

class AgentLoop:
    """
    The core Agent Loop engine.

    Usage:
        # DeepSeek (OpenAI compatible)
        agent = AgentLoop(provider="deepseek", api_key="sk-xxx")

        # Anthropic (Claude)
        agent = AgentLoop(provider="anthropic", api_key="sk-ant-xxx")

        response = agent.chat("帮我把桌面整理一下")
    """

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
          if provider == "deepseek":
              api_key = os.getenv("DEEPSEEK_API_KEY")
          elif provider == "anthropic":
              api_key = os.getenv("ANTHROPIC_API_KEY")
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

        # Conversation history (short-term memory)
        self.messages: list[dict] = []

        # Long-term memory (ChromaDB-backed, survives restarts)
        self.memory = get_memory()

        # Stats for observability
        self.stats = {
            "total_iterations": 0,
            "total_tool_calls": 0,
            "total_tokens": 0,
        }

    # ── Public API ────────────────────────────

    def chat(self, user_input: str, verbose: bool = True) -> str:
        """Process a single user message through the Agent Loop."""
        self.messages.append({"role": "user", "content": user_input})

        # ── Pre-fetch relevant memories ──────────
        relevant = self.memory.recall(user_input, n_results=3)
        self._memory_context = self.memory.format_for_prompt(relevant)
        if verbose and self._memory_context:
            print(f"🧠 Loaded {len(relevant)} relevant memories")

        # ── Final answer (captured for auto-summary) ──
        final_answer = ""

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
                final_answer = final_text
                # Auto-save important facts to long-term memory
                self._auto_remember(user_input, final_answer)
                return final_answer

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

        final_answer = (
            f"⚠️ Reached max iterations ({self.max_iterations}). "
            "The task may be too complex. Try breaking it into smaller steps."
        )
        self._auto_remember(user_input, final_answer)
        return final_answer

    def reset(self):
        """Clear conversation history and stats."""
        self.messages = []
        self._memory_context = ""
        self.stats = {"total_iterations": 0, "total_tool_calls": 0, "total_tokens": 0}

    # ── Memory Integration ─────────────────────

    def _build_system_prompt(self) -> str:
        """Build the system prompt, optionally augmented with relevant memories."""
        if self._memory_context:
            return SYSTEM_PROMPT + "\n\n" + self._memory_context
        return SYSTEM_PROMPT

    def _auto_remember(self, user_input: str, agent_response: str) -> None:
        """
        Auto-extract and store important facts after each conversation turn.
        Uses simple heuristic pattern matching (Phase 1).
        Phase 2 will use an LLM call for smarter extraction.
        """
        try:
            self.memory.summarize_and_remember(user_input, agent_response)
        except Exception:
            pass  # Memory failure should never break the chat

    # ── LLM Calls ─────────────────────────────

    def _call_deepseek(self):
        """Send conversation to DeepSeek (OpenAI-compatible API)."""
        t0 = time.time()

        # Build messages with system prompt (includes relevant memories)
        api_messages = [{"role": "system", "content": self._build_system_prompt()}] + self.messages

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
            system=self._build_system_prompt(),
            messages=self.messages,
            tools=TOOL_DEFINITIONS,
        )
        elapsed = time.time() - t0

        usage = response.usage
        self.stats["total_tokens"] += usage.input_tokens + usage.output_tokens

        print(f"  ⏱️  Claude: {elapsed:.1f}s | "
              f"in={usage.input_tokens} out={usage.output_tokens} tokens")

        return response

    # ── Response Parsing ──────────────────────

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

    # ── Tool Execution ────────────────────────

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


# ──────────────────────────────────────────────
# Quick test
# ──────────────────────────────────────────────

def demo():
    """Quick demo to verify the Agent Loop works."""
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    model = os.getenv("LLM_MODEL", "deepseek-chat")

    if not api_key:
        print("❌ No API key found. Please set DEEPSEEK_API_KEY or ANTHROPIC_API_KEY in .env")
        return

    agent = AgentLoop(provider=provider, api_key=api_key, model=model, max_iterations=5)

    print("=" * 60)
    print(f"🤖 Personal AI Assistant — Demo ({provider}: {model})")
    print("=" * 60)

    # Test: multi-step task
    prompt = "请做两件事：1. 告诉我现在的时间 2. 在当前目录创建一个 hello.txt，内容是 'Hello from my Agent!'"
    print(f"\n👤 User: {prompt}\n")

    response = agent.chat(prompt)
    print(f"\n{'=' * 60}")
    print(f"✅ Final response:\n{response}")
    print(f"\n📊 Stats: {json.dumps(agent.stats, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    demo()
