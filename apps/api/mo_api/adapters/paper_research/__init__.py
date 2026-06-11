"""PaperResearch 适配器包。"""

from .base import (
    PaperAnswer,
    PaperContext,
    PaperResearchAdapter,
    PaperResearchError,
    WebResearchAdapter,
    WebResearchResult,
    WebSource,
)
from .gpt_researcher_adapter import GPTResearcherAdapter
from .paperqa_adapter import PaperQAAdapter

__all__ = [
    "GPTResearcherAdapter",
    "PaperAnswer",
    "PaperContext",
    "PaperQAAdapter",
    "PaperResearchAdapter",
    "PaperResearchError",
    "WebResearchAdapter",
    "WebResearchResult",
    "WebSource",
]
