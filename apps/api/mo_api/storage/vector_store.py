"""Chroma 持久化向量库（按 task 隔离）。"""

from __future__ import annotations

import asyncio
import os
from typing import Any

from ..config import get_settings

_CHUNK_SIZE = 1500
_OVERLAP = 200


def _chunk_text(
    text: str, size: int = _CHUNK_SIZE, overlap: int = _OVERLAP
) -> list[str]:
    if not text:
        return []
    if overlap >= size:
        overlap = size // 2
    step = size - overlap
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + size])
        if i + size >= len(text):
            break
        i += step
    return chunks


class TaskVectorStore:
    """每个 task 一个 Chroma collection。"""

    def __init__(self, task_id: str, persist_dir: str | None = None) -> None:
        self.task_id = task_id
        settings = get_settings()
        base = persist_dir or settings.chroma_index_dir
        self._persist_dir = os.path.join(base, task_id)
        self._collection_name = f"mo_task_{task_id}"
        self._client: Any = None
        self._collection: Any = None

    def _ensure_collection(self) -> Any:
        if self._collection is not None:
            return self._collection
        os.makedirs(self._persist_dir, exist_ok=True)
        import chromadb

        self._client = chromadb.PersistentClient(path=self._persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"task_id": self.task_id},
        )
        return self._collection

    async def add_chunks(
        self, content: dict[str, str], *, source_uri: str
    ) -> int:
        """将文件内容切块写入向量库，metadata 含 locator 与 source_uri。"""

        def _add() -> int:
            collection = self._ensure_collection()
            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict[str, str]] = []
            count = 0
            for path, file_content in content.items():
                chunks = _chunk_text(file_content)
                for idx, chunk in enumerate(chunks):
                    chunk_id = f"{path}::{idx}"
                    ids.append(chunk_id)
                    documents.append(chunk)
                    metadatas.append({"locator": path, "source_uri": source_uri})
                    count += 1
            if ids:
                # ChromaDB Rust 后端单批上限 5461；大仓库分批写入
                _BATCH = 5000
                for start in range(0, len(ids), _BATCH):
                    collection.add(
                        ids=ids[start:start + _BATCH],
                        documents=documents[start:start + _BATCH],
                        metadatas=metadatas[start:start + _BATCH],
                    )
            return count

        return await asyncio.to_thread(_add)

    async def query(self, text: str, n: int = 5) -> list[dict[str, str]]:
        """检索相似块，返回 document / locator / source_uri。"""

        def _query() -> list[dict[str, str]]:
            collection = self._ensure_collection()
            if collection.count() == 0:
                return []
            result = collection.query(query_texts=[text], n_results=min(n, collection.count()))
            documents = (result.get("documents") or [[]])[0]
            metadatas = (result.get("metadatas") or [[]])[0]
            rows: list[dict[str, str]] = []
            for doc, meta in zip(documents, metadatas):
                meta = meta or {}
                rows.append(
                    {
                        "document": doc or "",
                        "locator": str(meta.get("locator", "")),
                        "source_uri": str(meta.get("source_uri", "")),
                    }
                )
            return rows

        return await asyncio.to_thread(_query)
