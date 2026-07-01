"""
Phase 1 / Week 3: Memory System — long-term memory for the Personal AI Assistant.

Uses ChromaDB as the vector store:
  - Each memory is a text chunk stored as an embedding vector.
  - On recall, we search by semantic similarity (not keyword).
  - Memories persist to disk, surviving process restarts.

Architecture:
  MemoryManager
    ├── remember(text, metadata)   → store a memory
    ├── recall(query, n)            → retrieve top-n relevant memories
    ├── forget(memory_id)           → delete a memory
    └── summarize_and_remember(conversation) → auto-extract key facts
"""

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────

# ChromaDB stores everything under this directory
MEMORY_DIR = Path.home() / ".personal_ai_assistant_memory"

# ──────────────────────────────────────────────
# Memory Manager
# ──────────────────────────────────────────────

class MemoryManager:
    """
    High-level API for the Agent's long-term memory.

    Usage:
        mem = MemoryManager()
        mem.remember("User's cat is named 橘子", metadata={"topic": "pet"})
        results = mem.recall("What's the cat's name?", n_results=3)
        mem.forget(memory_id)
    """

    def __init__(self, collection_name: str = "agent_memory"):
        # Ensure the storage directory exists
        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        # Persistent ChromaDB client — data survives restarts
        self.client = chromadb.PersistentClient(
            path=str(MEMORY_DIR),
            settings=Settings(anonymized_telemetry=False),
        )

        # Uses ChromaDB's built-in ONNX embedding function.
        # Downloads all-MiniLM-L6-v2 (~80 MB) on first use. No API key, no GPU needed.
        # If you want to switch to a different embedding model later:
        #   from chromadb.utils import embedding_functions
        #   self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(...)
        #   Then pass embedding_function=self.embed_fn to get_or_create_collection.

        # Get or create a collection (like a "table" in SQL)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Personal AI Assistant long-term memory"},
        )

    # ── CRUD Operations ────────────────────────

    def remember(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
        memory_id: str | None = None,
    ) -> str:
        """
        Store a memory. Returns the memory ID.

        Args:
            text: The fact or conversation snippet to remember.
            metadata: Optional tags (topic, date, importance, etc.).
            memory_id: Optional custom ID. Auto-generated if omitted.
        """
        mid = memory_id or str(uuid.uuid4())[:8]
        meta = metadata or {}
        meta.setdefault("stored_at", datetime.now().isoformat())
        meta.setdefault("char_count", len(text))

        self.collection.add(
            ids=[mid],
            documents=[text],
            metadatas=[meta],
        )
        return mid

    def recall(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """
        Search memory for facts semantically similar to the query.

        Returns a list of dicts with keys: id, text, metadata, distance.
        Lower distance = more relevant.
        """
        if self.collection.count() == 0:
            return []

        results = self.collection.query(
            query_texts=[query],
            n_results=min(n_results, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        memories = []
        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        for i, doc, meta, dist in zip(ids, docs, metas, dists):
            memories.append({
                "id": i,
                "text": doc,
                "metadata": meta,
                "distance": dist,
            })

        return memories

    def forget(self, memory_id: str) -> bool:
        """Delete a memory by ID. Returns True if it existed."""
        try:
            self.collection.delete(ids=[memory_id])
            return True
        except Exception:
            return False

    def summarize_and_remember(self, user_msg: str, agent_response: str) -> str | None:
        """
        Extract key facts from a conversation turn and store them.

        Uses simple heuristics for now (Phase 1).
        Phase 2 will use an LLM call to summarize.

        Returns the memory ID if something was stored, else None.
        """
        # Heuristic: if the user's message looks like a preference or fact,
        # store it. We look for key patterns.
        fact_patterns = [
            "我叫", "我的名字", "我是",           # name
            "我喜欢", "我不喜欢", "我讨厌",        # preference
            "我的猫", "我的狗", "我的宠物",        # pet
            "我住在", "我在",                      # location
            "记住", "记下",                        # explicit remember
        ]

        combined = user_msg + " " + agent_response

        for pattern in fact_patterns:
            if pattern in combined:
                return self.remember(
                    text=f"[{datetime.now().strftime('%Y-%m-%d')}] {combined[:500]}",
                    metadata={
                        "type": "auto_summary",
                        "pattern": pattern,
                    },
                )

        return None

    # ── Utility ────────────────────────────────

    def count(self) -> int:
        """Return total number of stored memories."""
        return self.collection.count()

    def clear(self) -> None:
        """Delete ALL memories. Irreversible."""
        ids = self.collection.get()["ids"]
        if ids:
            self.collection.delete(ids=ids)

    def format_for_prompt(self, memories: list[dict[str, Any]]) -> str:
        """
        Format retrieved memories as a string to inject into the system prompt.

        Args:
            memories: List from recall().

        Returns:
            A formatted string ready for the LLM, or empty string if no memories.
        """
        if not memories:
            return ""

        lines = ["## 🧠 Relevant Memories (from past conversations)"]
        for i, m in enumerate(memories, 1):
            stored = m.get("metadata", {}).get("stored_at", "unknown")[:10]
            lines.append(f"{i}. [{stored}] {m['text'][:300]}")

        return "\n".join(lines)


# ──────────────────────────────────────────────
# Module-level convenience (singleton pattern)
# ──────────────────────────────────────────────

_memory_manager: MemoryManager | None = None


def get_memory() -> MemoryManager:
    """Get or create the global MemoryManager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
