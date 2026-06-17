"""PaperQA 端到端验证：deepseek-v4-pro LLM + DashScope Qwen Embedding。

验证完整链路：
1. litellm 直连 deepseek-v4-pro
2. DashScopeEmbeddingModel 独立调用
3. paper-qa aadd (Qwen embedding) + aquery (deepseek-v4-pro)
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "apps" / "api"))

# 加载 .env
_ENV_FILE = _PROJECT_ROOT / ".env"
if _ENV_FILE.is_file():
    with open(_ENV_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() and key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip()


async def main():
    results: dict[str, bool] = {}

    # ── Step 1: litellm LLM 直连 ──
    print("=" * 60)
    print("[Step 1] litellm.completion(deepseek-v4-pro)")
    from mo_api.adapters.paper_research.paperqa_adapter import (
        _register_deepseek_v4_models,
    )
    _register_deepseek_v4_models()

    import litellm

    resp = litellm.completion(
        model="deepseek/deepseek-v4-pro",
        messages=[{"role": "user", "content": "Reply OK in one word."}],
        max_tokens=128,
    )
    llm_content = resp.choices[0].message.content
    llm_tokens = resp.usage.total_tokens
    print(f"  content='{llm_content}' tokens={llm_tokens}")
    assert llm_content, "LLM should return non-empty content"
    results["llm_direct"] = True
    print("  => PASSED\n")

    # ── Step 2: DashScopeEmbeddingModel 独立调用 ──
    print("[Step 2] DashScopeEmbeddingModel.embed_documents()")
    from mo_api.adapters.embeddings import DashScopeEmbeddingModel

    qwen_key = os.environ.get("QWEN_API_KEY", "")
    print(f"  QWEN_API_KEY: {'configured (' + qwen_key[:8] + '...)' if qwen_key else 'MISSING'}")

    emb_model = DashScopeEmbeddingModel(
        name="tongyi-embedding-vision-plus-2026-03-06",
        api_key=qwen_key,
        dimension=1152,
    )
    texts = [
        "MO is a research repository survey and planning assistant.",
        "The backend uses FastAPI and LangGraph for workflow orchestration.",
    ]
    vectors = await emb_model.embed_documents(texts)
    print(f"  texts={len(texts)} vectors={len(vectors)} dims=[{len(vectors[0]) if vectors else 0}]")
    assert len(vectors) == 2, f"Expected 2 vectors, got {len(vectors)}"
    assert len(vectors[0]) == 1152, f"Expected 1152 dims, got {len(vectors[0])}"
    results["dashscope_embedding"] = True
    print("  => PASSED\n")

    # ── Step 3: paper-qa aadd (Qwen embedding) + aquery (deepseek LLM) ──
    print("[Step 3] paper-qa aadd(Qwen) + aquery(deepseek-v4-pro)")

    test_dir = _PROJECT_ROOT / "scripts" / "runtime" / "paper_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_paper.txt"
    test_file.write_text("""# MO Project Overview

MO is a research repository survey and planning assistant built with
FastAPI (backend) and React/Vite (frontend).

## Architecture

The backend uses LangGraph for workflow orchestration. Key nodes:
- repo_ingest: Clone and analyze GitHub repositories via gitingest
- code_understanding: Extract core modules and execution paths using LLM
- paper_research: RAG-based paper Q&A via PaperQA library
- reproducibility: Score projects on reproducibility dimensions
- comparison_builder: Multi-repo comparison

The ModelGateway routes requests by LLM capability (reasoning, vision,
json_mode) to different model providers (DeepSeek, Kimi) using LiteLLM.

The project was developed in milestones M0 through M10.
""", encoding="utf-8")

    from paperqa import Docs, Settings

    settings = Settings(
        llm="deepseek/deepseek-v4-pro",
        summary_llm="deepseek/deepseek-v4-pro",
        embedding="sparse",  # Settings 占位；实际 embedding_model 直接传入
    )
    docs = Docs()
    await docs.aadd(str(test_file), settings=settings, embedding_model=emb_model)
    print(f"  aadd: OK (Qwen embedding, {len(docs.texts)} chunks)")

    session = await docs.aquery(
        "What architecture does MO use and what are its main components?",
        settings=settings,
        embedding_model=emb_model,
    )
    answer = getattr(session, "answer", "") or ""
    contexts = list(getattr(session, "contexts", []) or [])
    print(f"  aquery: answer_len={len(answer)}, contexts={len(contexts)}")
    for i, c in enumerate(contexts[:2]):
        txt = getattr(c, "text", "") or ""
        txt_str = getattr(txt, "text", str(txt)) if not isinstance(txt, str) else txt
        print(f"  [{i}] {txt_str[:100]}")

    assert answer, "aquery should return non-empty answer"
    assert len(contexts) > 0, "aquery should return contexts"
    results["paperqa_full_pipeline"] = True
    print("  => PASSED\n")

    # ── Step 4: PaperQAAdapter 集成验证 ──
    print("[Step 4] PaperQAAdapter._resolve_embedding_model()")
    from mo_api.adapters.paper_research import PaperQAAdapter

    adapter = PaperQAAdapter()
    resolved = adapter._resolve_embedding_model()
    if resolved is not None:
        print(f"  model: {resolved.name}")
        print(f"  dimension: {resolved.dimension}")
        results["adapter_resolve"] = True
        print("  => PASSED\n")
    else:
        print("  WARNING: embedding model not resolved (QWEN_API_KEY may be missing)")
        results["adapter_resolve"] = False

    # ── 汇总 ──
    print("=" * 60)
    all_pass = all(results.values())
    print(f"Results: {len(results)} checks, {sum(results.values())} passed")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'} {name}")
    print(f"\n{'ALL PASSED' if all_pass else 'SOME FAILED'}")
    test_file.unlink(missing_ok=True)
    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
