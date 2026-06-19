"""Report v2 LLM prompts — JSON-structured output for report narratives."""

from __future__ import annotations

REPORT_SYSTEM_PROMPT_ZH = """
你是 MO 的科研仓库调研报告撰写器。你的任务是把结构化仓库证据转成面向人阅读的报告草稿。

硬性规则：
1. 只能使用输入 JSON 中提供的信息，不得编造事实。
2. 不知道就写 unknown / pending，不要猜。
3. evidence_ids 必须来自输入，不得新造 id。
4. fact 只能来自强证据：user_confirmation、strong repo_file、strong official_doc、run_log。
5. model_inference 只能支持 inference，不能单独支持 fact。
6. recommendation 必须基于 evidence_ids，且 requires_user_review=true。
7. 无 run_log 时，不得声称复现成功；只能说 static_reproducibility_assessment。
8. 输出必须是合法 JSON，不要输出 Markdown 代码块。
9. 正文不要堆砌 evidence id、node id、tool enum。证据只放 evidence_ids 字段。
"""

REPO_NARRATIVE_PROMPT_ZH = """根据以下仓库卡片和证据摘要，为每个仓库生成面向人的解释。

输出 JSON schema:
{
  "repos": [
    {
      "repo_url": "...",
      "what_it_is": "这个仓库是什么，一句话",
      "problem_solved": "它解决什么问题",
      "tech_stack": ["语言/框架/依赖/构建工具"],
      "architecture": ["核心模块或执行路径"],
      "maturity_summary": "文档、示例、测试、入口的成熟度判断",
      "suitable_for": ["适用场景"],
      "risks": ["风险或未知项"],
      "claims": [
        {
          "claim": "...",
          "label": "fact|inference|recommendation|pending",
          "confidence": 0.0,
          "evidence_ids": ["只能来自输入"],
          "requires_user_review": false
        }
      ]
    }
  ]
}

输入：
{context_json}
"""

COMPARISON_SYNTHESIS_PROMPT_ZH = """根据多仓库对比矩阵、复现性评估和用户目标，生成对比结论。

必须先输出结论，再解释分数。不要只复述矩阵。

输出 JSON schema:
{
  "summary": "整体对比结论",
  "best_overall": "repo name or unknown",
  "scenario_recommendations": [
    {
      "scenario": "快速 demo|论文复现|工程集成|二次开发",
      "recommendation": "推荐仓库或 pending",
      "rationale": "为什么",
      "evidence_ids": ["..."],
      "requires_user_review": true
    }
  ],
  "limitations": ["..."],
  "claims": [
    {
      "claim": "...",
      "label": "inference|recommendation|pending",
      "confidence": 0.0,
      "evidence_ids": ["..."],
      "requires_user_review": true
    }
  ]
}

输入：
{context_json}
"""

RISK_SYNTHESIS_PROMPT_ZH = """根据计划未知项、仓库风险、weak/missing evidence、复现缺失信息，按用户影响排序风险。

风险分组必须包含：
- 阻塞型风险
- 结果可信度风险
- 工程集成风险
- 维护/依赖风险
- 证据不足风险

输出 JSON schema:
{
  "risk_groups": [
    {
      "group": "阻塞型风险",
      "items": [
        {
          "risk": "...",
          "impact": "...",
          "next_check": "...",
          "evidence_ids": ["..."],
          "label": "pending|inference"
        }
      ]
    }
  ],
  "claims": [...]
}

输入：
{context_json}
"""

TECH_ROUTE_SYNTHESIS_PROMPT_ZH = """根据仓库卡片和代码洞察，分析技术路线与架构。

输出 JSON schema:
{
  "repos": [
    {
      "repo_url": "...",
      "core_modules": ["..."],
      "execution_flow": "...",
      "dependency_boundary": "...",
      "architecture_notes": "...",
      "claims": [...]
    }
  ]
}

输入：
{context_json}
"""

# -- 兼容旧调用（不抛出 ModuleNotFoundError） --

REPORT_SYSTEM_PROMPT_EN = REPORT_SYSTEM_PROMPT_ZH  # 简化：英文复用相同规则
