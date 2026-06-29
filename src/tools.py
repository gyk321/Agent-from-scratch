"""
Phase 1 / Week 1: Tool definitions for the Personal AI Assistant.

每个工具都是一个函数 + 一个描述（给 LLM 看的 schema）。
LLM 看到的是 tool schema，用户代码执行的是 tool function。
"""

import os
import subprocess
import sqlite3
import json
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ──────────────────────────────────────────────
# Tool: File Operations
# ──────────────────────────────────────────────

def read_file(filepath: str, max_lines: int = 100) -> str:
    """Read content from a file."""
    path = Path(filepath).expanduser()
    if not path.exists():
        return f"[Error] File not found: {filepath}"
    try:
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        if len(lines) > max_lines:
            return "\n".join(lines[:max_lines]) + f"\n... (truncated, total {len(lines)} lines)"
        return content
    except Exception as e:
        return f"[Error] Failed to read file: {e}"


def write_file(filepath: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed."""
    path = Path(filepath).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(content, encoding="utf-8")
        return f"[OK] Written {len(content)} chars to {filepath}"
    except Exception as e:
        return f"[Error] Failed to write file: {e}"


def list_files(directory: str = ".") -> str:
    """List files in a directory."""
    path = Path(directory).expanduser()
    if not path.exists():
        return f"[Error] Directory not found: {directory}"
    try:
        items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        lines = []
        for item in items[:50]:
            tag = "📁" if item.is_dir() else "📄"
            try:
                size = item.stat().st_size
            except OSError:
                size = 0
            lines.append(f"{tag} {item.name} ({_human_size(size)})")
        return "\n".join(lines)
    except Exception as e:
        return f"[Error] Failed to list directory: {e}"


# ──────────────────────────────────────────────
# Tool: Shell Command Execution
# ──────────────────────────────────────────────

# 🔒 安全白名单：只允许这些命令前缀
ALLOWED_COMMANDS = [
    "dir", "ls", "echo", "type", "cat", "cd", "pwd",
    "python", "python3", "pip", "node", "npm",
    "git", "date", "time", "find", "grep", "wc",
    "mkdir", "copy", "move", "ren", "del", "rm",
]

def shell_exec(command: str, timeout: int = 30) -> str:
    """
    Execute a shell command. ⚠️ Only whitelisted commands are allowed.
    Commands run in the project working directory.
    """
    cmd_parts = command.strip().split()
    if not cmd_parts:
        return "[Error] Empty command"

    base_cmd = cmd_parts[0].lower()
    if base_cmd not in [c.lower() for c in ALLOWED_COMMANDS]:
        return f"[Blocked] Command '{base_cmd}' not in allowed list. Allowed: {', '.join(ALLOWED_COMMANDS)}"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(Path.cwd())
        )
        output = result.stdout.strip() or result.stderr.strip() or "(no output)"
        if len(output) > 2000:
            output = output[:2000] + "\n... (truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"[Error] Command timed out after {timeout}s"
    except Exception as e:
        return f"[Error] {e}"


# ──────────────────────────────────────────────
# Tool: Web Operations
# ──────────────────────────────────────────────

def web_fetch(url: str) -> str:
    """Fetch and extract text content from a web page."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; PersonalAIAssistant/1.0)"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style tags
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Remove excessive blank lines
        lines = [line for line in text.split("\n") if line.strip()]
        text = "\n".join(lines)

        if len(text) > 3000:
            text = text[:3000] + "\n... (truncated)"
        return text
    except Exception as e:
        return f"[Error] Failed to fetch {url}: {e}"


def web_search_notes(query: str) -> str:
    """
    ⚠️ Placeholder for web search.
    In Phase 2 we'll hook this into a real search API (Tavily, SerpAPI, etc.)
    For now, this is a reminder that your Agent should be able to search the web.
    """
    return (
        f"[Note] Web search is a Phase 2 feature.\n"
        f"Query: {query}\n"
        f"Suggested: Use web_fetch() to fetch a specific URL, or ask the user "
        f"to provide the information directly."
    )


# ──────────────────────────────────────────────
# Tool: Database (SQLite)
# ──────────────────────────────────────────────

DB_PATH = Path.home() / ".personal_ai_assistant.db"


def db_query(sql: str) -> str:
    """Execute a read-only SQL query on the local SQLite database."""
    if not DB_PATH.exists():
        return "[Error] Database not initialized. Use db_init() first."
    # Safety: only allow SELECT
    if not sql.strip().upper().startswith("SELECT"):
        return "[Blocked] Only SELECT queries are allowed for safety."
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description] if cursor.description else []
        conn.close()

        if not rows:
            return "(no results)"

        # Format as table
        lines = [" | ".join(cols), "-" * 40]
        for row in rows[:20]:
            lines.append(" | ".join(str(v) for v in row))
        if len(rows) > 20:
            lines.append(f"... and {len(rows) - 20} more rows")
        return "\n".join(lines)
    except Exception as e:
        return f"[Error] {e}"


def db_exec(sql: str) -> str:
    """Execute a write SQL statement (INSERT, UPDATE, DELETE, CREATE)."""
    if not sql.strip().upper().startswith(("INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER")):
        return "[Blocked] Only DML/DDL statements allowed."
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(sql)
        conn.commit()
        conn.close()
        return f"[OK] Executed: {sql[:80]}..."
    except Exception as e:
        return f"[Error] {e}"


# ──────────────────────────────────────────────
# Tool: Time & Date
# ──────────────────────────────────────────────

def get_current_time() -> str:
    """Get the current date and time."""
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S %A (Week %W)")


# ──────────────────────────────────────────────
# Tool Registry — LLM calls tools by name
# ──────────────────────────────────────────────

# 给 LLM 看的工具描述（Anthropic tool-use format）
TOOL_DEFINITIONS = [
    {
        "name": "read_file",
        "description": "Read content from a file. Use to check existing code, notes, or data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the file to read"},
                "max_lines": {"type": "integer", "description": "Max lines to return (default 100)"},
            },
            "required": ["filepath"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories automatically.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filepath": {"type": "string", "description": "Path to the file to write"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["filepath", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory. Use to explore the file system.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory path (default: current dir)"},
            },
            "required": [],
        },
    },
    {
        "name": "shell_exec",
        "description": "Execute a shell command (whitelisted commands only). Use for git, python, npm, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "web_fetch",
        "description": "Fetch and extract text content from a URL. Use to read documentation, articles, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search_notes",
        "description": "Placeholder for web search (Phase 2 feature). For now, use web_fetch for specific URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "db_query",
        "description": "Execute a read-only SQL SELECT query on the local database.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL SELECT query"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "db_exec",
        "description": "Execute a write SQL statement (INSERT, UPDATE, DELETE, CREATE TABLE, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL write statement"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Get the current date and time.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

# 函数名 → 函数对象的映射
TOOL_MAP = {
    "read_file": read_file,
    "write_file": write_file,
    "list_files": list_files,
    "shell_exec": shell_exec,
    "web_fetch": web_fetch,
    "web_search_notes": web_search_notes,
    "db_query": db_query,
    "db_exec": db_exec,
    "get_current_time": get_current_time,
}


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.0f}{unit}"
        size_bytes /= 1024
    return f"{size_bytes:.0f}TB"
