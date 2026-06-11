"""RepoIngest 适配层。"""

from .gitingest_adapter import GitingestAdapter, RepoIngestError

__all__ = ["GitingestAdapter", "RepoIngestError"]
