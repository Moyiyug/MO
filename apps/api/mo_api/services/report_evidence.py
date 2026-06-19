"""证据摘要与 Claim 工厂（Report v2）。"""

from __future__ import annotations

import uuid
from collections import defaultdict

from pydantic import BaseModel, Field

from ..models.enums import ClaimLabel, EvidenceStrength, SourceType
from ..models.evidence import EvidenceItem, ReportClaim


class EvidenceRef(BaseModel):
    """单条证据的可读引用。"""

    evidence_id: str
    display_id: str  # E01, E02, ...
    source_type: SourceType
    strength: EvidenceStrength
    source_uri: str
    locator: str | None = None
    summary: str
    material_type: str | None = None


class EvidenceDigest(BaseModel):
    """批量证据的摘要索引。"""

    refs: list[EvidenceRef] = Field(default_factory=list)
    by_id: dict[str, EvidenceRef] = Field(default_factory=dict)
    by_repo_url: dict[str, list[EvidenceRef]] = Field(default_factory=dict)
    by_source_type: dict[str, list[EvidenceRef]] = Field(default_factory=dict)
    weak_or_missing_ids: list[str] = Field(default_factory=list)

    def label_for(self, evidence_id: str) -> str:
        """返回友好编号（E01），降级为 evidence_id 前 8 字符。"""
        ref = self.by_id.get(evidence_id)
        return ref.display_id if ref else evidence_id[:8]

    def markdown_refs(self, evidence_ids: list[str]) -> str:
        """返回 Markdown 格式的证据引用文本。"""
        labels = [self.label_for(eid) for eid in evidence_ids if eid in self.by_id]
        return f"（证据：{', '.join(labels)}）" if labels else ""

    def add_item(self, item: EvidenceItem) -> EvidenceRef:
        """动态添加一条证据（用于报告生成期间新创建的 evidence）。"""
        idx = len(self.refs) + 1
        ref = EvidenceRef(
            evidence_id=item.id,
            display_id=f"E{idx:02d}",
            source_type=item.source_type,
            strength=item.strength,
            source_uri=item.source_uri,
            locator=item.locator,
            summary=item.quote_or_summary.replace("\n", " ")[:500],
            material_type=item.material_type.value if item.material_type else None,
        )
        self.refs.append(ref)
        self.by_id[item.id] = ref
        self.by_source_type.setdefault(item.source_type.value, []).append(ref)
        if item.strength in (EvidenceStrength.WEAK, EvidenceStrength.MISSING):
            self.weak_or_missing_ids.append(item.id)
        return ref


def build_evidence_digest(items: list[EvidenceItem]) -> EvidenceDigest:
    """将 EvidenceItem 列表转为 EvidenceDigest。"""
    refs: list[EvidenceRef] = []
    by_id: dict[str, EvidenceRef] = {}
    by_repo_url: dict[str, list[EvidenceRef]] = defaultdict(list)
    by_source_type: dict[str, list[EvidenceRef]] = defaultdict(list)
    weak_or_missing_ids: list[str] = []

    for idx, item in enumerate(items, 1):
        ref = EvidenceRef(
            evidence_id=item.id,
            display_id=f"E{idx:02d}",
            source_type=item.source_type,
            strength=item.strength,
            source_uri=item.source_uri,
            locator=item.locator,
            summary=item.quote_or_summary.replace("\n", " ")[:500],
            material_type=item.material_type.value if item.material_type else None,
        )
        refs.append(ref)
        by_id[item.id] = ref
        by_source_type[item.source_type.value].append(ref)
        if item.strength in (EvidenceStrength.WEAK, EvidenceStrength.MISSING):
            weak_or_missing_ids.append(item.id)
        # repo_url 归组：后续可通过 RepoCard.evidence_ids 增强。
        for eid in (item.used_by or []):
            # used_by 存储的是 claim id，不直接映射 repo。
            # 这里仅按 source_uri 做粗略归组。
            pass
        # 简单按 source_uri 前缀归组
        repo_key = item.source_uri.rstrip("/").rsplit("/tree/", 1)[0]
        if "github.com" in repo_key:
            by_repo_url[repo_key].append(ref)

    return EvidenceDigest(
        refs=refs,
        by_id=by_id,
        by_repo_url=dict(by_repo_url),
        by_source_type=dict(by_source_type),
        weak_or_missing_ids=weak_or_missing_ids,
    )


class ClaimFactory:
    """集中守住 R-003 证据铁律的 Claim 工厂。"""

    def __init__(self, digest: EvidenceDigest) -> None:
        self.digest = digest

    def evidence_label_for_claim(
        self,
        *,
        desired: ClaimLabel,
        evidence_ids: list[str],
        requires_user_review: bool = False,
    ) -> tuple[ClaimLabel, bool]:
        """根据证据情况降级 claim label，确保不违反 R-003。"""
        eids = [eid for eid in evidence_ids if eid in self.digest.by_id]
        if desired is not ClaimLabel.PENDING and not eids:
            return ClaimLabel.PENDING, True

        if any(eid in self.digest.weak_or_missing_ids for eid in eids):
            return ClaimLabel.PENDING, True

        # model_inference 不能成为 fact 的唯一依据。
        if desired is ClaimLabel.FACT:
            refs = [self.digest.by_id[eid] for eid in eids]
            allowed_fact_sources = {
                SourceType.USER_CONFIRMATION,
                SourceType.REPO_FILE,
                SourceType.RUN_LOG,
            }
            if not refs or not all(r.source_type in allowed_fact_sources for r in refs):
                return ClaimLabel.INFERENCE, True
            if not all(r.strength is EvidenceStrength.STRONG for r in refs):
                return ClaimLabel.INFERENCE, True

        if desired is ClaimLabel.RECOMMENDATION:
            # 推荐应需要用户审阅，避免绕过 R-004 的最终强推荐。
            requires_user_review = True

        return desired, requires_user_review

    def make(
        self,
        text: str,
        label: ClaimLabel,
        evidence_ids: list[str] | None = None,
        *,
        confidence: float = 0.5,
        requires_user_review: bool = False,
    ) -> ReportClaim:
        """创建 ReportClaim，自动降级标签。"""
        eids = list(dict.fromkeys(evidence_ids or []))
        label, requires_user_review = self.evidence_label_for_claim(
            desired=label,
            evidence_ids=eids,
            requires_user_review=requires_user_review,
        )
        return ReportClaim(
            id=uuid.uuid4().hex,
            claim=text.strip()[:2000],
            label=label,
            evidence_ids=eids if label is not ClaimLabel.PENDING else eids,
            confidence=confidence,
            requires_user_review=requires_user_review,
        )


def format_claim_for_markdown(
    claim: ReportClaim,
    digest: EvidenceDigest | None = None,
    *,
    lang: str = "zh",
) -> str:
    """将 ReportClaim 格式化为面向人阅读的 Markdown 行。

    正文使用友好编号（E01/E02），不暴露 raw evidence id。
    结构化 claim 仍保留真实 evidence_ids。
    """
    label_map_zh = {
        ClaimLabel.FACT: "事实",
        ClaimLabel.INFERENCE: "推断",
        ClaimLabel.RECOMMENDATION: "建议",
        ClaimLabel.PENDING: "待确认",
    }
    label_map_en = {
        ClaimLabel.FACT: "fact",
        ClaimLabel.INFERENCE: "inference",
        ClaimLabel.RECOMMENDATION: "recommendation",
        ClaimLabel.PENDING: "pending",
    }
    label_map = label_map_zh if lang == "zh" else label_map_en
    label_text = label_map.get(claim.label, claim.label.value)

    refs = ""
    if digest and claim.evidence_ids:
        refs = digest.markdown_refs(claim.evidence_ids)
    review = "（需人工审阅）" if claim.requires_user_review else ""
    return f"- **[{label_text}]** {claim.claim}{refs}{review}"
