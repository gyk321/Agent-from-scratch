"""
Phase 1: Personal AI Assistant — Interactive Chat Interface.

Usage:
    python -m src.main

This is the main entry point for your Personal AI Assistant.
It provides an interactive REPL loop where you can chat with your Agent.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from src.agent import AgentLoop

# Load .env
load_dotenv(project_root / ".env")

console = Console()

BANNER = """
╔══════════════════════════════════════════════════════╗
║         🤖 Personal AI Assistant                     ║
║                                                      ║
║  Phase 1 — Building an Agent with Memory & Tools     ║
║                                                      ║
║  Commands:                                           ║
║    /stats   — Show Agent stats                       ║
║    /reset   — Clear conversation history             ║
║    /help    — Show this help                         ║
║    /quit    — Exit                                   ║
╚══════════════════════════════════════════════════════╝
"""


def main():
    # ── Configuration ──────────────────────────
    provider = os.getenv("LLM_PROVIDER", "deepseek")
    api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        console.print("\n[red]❌ No API key found![/red]")
        console.print("\n请在 .env 文件中配置:")
        console.print("  DEEPSEEK_API_KEY=sk-xxx    (DeepSeek)")
        console.print("  ANTHROPIC_API_KEY=sk-ant-xxx  (Claude)\n")
        return

    model = os.getenv("LLM_MODEL", "deepseek-chat")

    console.print(BANNER, style="bold cyan")
    console.print(f"[dim]Provider: {provider}[/dim]")
    console.print(f"[dim]Model: {model}[/dim]")
    console.print(f"[dim]Working dir: {os.getcwd()}[/dim]\n")

    # ── Initialize Agent ───────────────────────
    agent = AgentLoop(provider=provider, api_key=api_key, model=model)

    # ── Interactive Loop ───────────────────────
    while True:
        try:
            user_input = console.input("[bold green]You ›[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Goodbye! 👋[/yellow]")
            break

        if not user_input:
            continue

        # Handle commands
        if user_input.startswith("/"):
            cmd = user_input[1:].lower()
            if cmd in ("quit", "exit", "q"):
                console.print("[yellow]Goodbye! 👋[/yellow]")
                break
            elif cmd == "stats":
                console.print(f"[dim]📊 Stats: {agent.stats}[/dim]")
                continue
            elif cmd == "reset":
                agent.reset()
                console.print("[dim]🔄 Conversation reset.[/dim]")
                continue
            elif cmd == "help":
                console.print(BANNER, style="bold cyan")
                continue
            else:
                console.print(f"[red]Unknown command: {user_input}[/red]")
                continue

        # Process user input through the Agent Loop
        console.print()
        try:
            response = agent.chat(user_input)
            console.print()
            console.print("[bold blue]Agent ›[/bold blue]")
            console.print(Markdown(response))
            console.print()
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")


if __name__ == "__main__":
    main()
