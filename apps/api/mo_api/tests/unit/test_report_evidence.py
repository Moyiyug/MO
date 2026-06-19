"""EvidenceDigest / ClaimFactory 单元测试（Phase A）。"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mo_api.models.enums import (
    ClaimLabel,
    EvidenceStrength,
    MaterialType,
    SourceType,
)
from mo_api.models.evidence import EvidenceItem
from mo_api.services.report_evidence import (
    ClaimFactory,
    build_evidence_digest,
)


def _make_evidence(
    eid: str,
    source_type: SourceType,
    strength: EvidenceStrength,
    summary: str = "test summary",
) -> EvidenceItem:
    return EvidenceItem(
        id=eid,
        task_id="t1",
        source_type=source_type,
        source_uri="https://example.com",
        locator="README.md",
        quote_or_summary=summary,
        strength=strength,
        material_type=MaterialType.OFFICIAL_DOC,
        created_at=datetime.now(timezone.utc),
    )


# -- EvidenceDigest --

def test_digest_assigns_stable_display_ids() -> None:
    items = [
        _make_evidence("eA", SourceType.REPO_FILE, EvidenceStrength.STRONG),
        _make_evidence("eB", SourceType.PAPER, EvidenceStrength.MEDIUM),
        _make_evidence("eC", SourceType.MODEL_INFERENCE, EvidenceStrength.WEAK),
    ]
    digest = build_evidence_digest(items)
    assert digest.label_for("eA") == "E01"
    assert digest.label_for("eB") == "E02"
    assert digest.label_for("eC") == "E03"
    assert digest.label_for("nonexistent") == "nonexist"


def test_digest_collects_weak_or_missing() -> None:
    items = [
        _make_evidence("e1", SourceType.REPO_FILE, EvidenceStrength.STRONG),
        _make_evidence("e2", SourceType.MODEL_INFERENCE, EvidenceStrength.WEAK),
        _make_evidence("e3", SourceType.WEB, EvidenceStrength.MISSING),
    ]
    digest = build_evidence_digest(items)
    assert "e2" in digest.weak_or_missing_ids
    assert "e3" in digest.weak_or_missing_ids
    assert "e1" not in digest.weak_or_missing_ids


def test_digest_groups_by_source_type() -> None:
    items = [
        _make_evidence("e1", SourceType.REPO_FILE, EvidenceStrength.STRONG),
        _make_evidence("e2", SourceType.PAPER, EvidenceStrength.MEDIUM),
        _make_evidence("e3", SourceType.REPO_FILE, EvidenceStrength.MEDIUM),
    ]
    digest = build_evidence_digest(items)
    assert len(digest.by_source_type.get("repo_file", [])) == 2
    assert len(digest.by_source_type.get("paper", [])) == 1


def test_digest_markdown_refs() -> None:
    items = [
        _make_evidence("eA", SourceType.REPO_FILE, EvidenceStrength.STRONG),
        _make_evidence("eB", SourceType.PAPER, EvidenceStrength.MEDIUM),
    ]
    digest = build_evidence_digest(items)
    refs = digest.markdown_refs(["eA", "eB"])
    assert "E01" in refs
    assert "E02" in refs
    # 不应包含 raw id
    assert "eA" not in refs

    # 未知 id 不在 by_id 中，所以不应产生引用
    refs2 = digest.markdown_refs(["unknown-id"])
    assert refs2 == ""


# -- ClaimFactory --

def test_claim_factory_downgrades_fact_from_model_inference() -> None:
    items = [
        _make_evidence("e1", SourceType.MODEL_INFERENCE, EvidenceStrength.MEDIUM),
    ]
    digest = build_evidence_digest(items)
    factory = ClaimFactory(digest)

    label, review = factory.evidence_label_for_claim(
        desired=ClaimLabel.FACT,
        evidence_ids=["e1"],
    )
    assert label is ClaimLabel.INFERENCE
    assert review is True


def test_claim_factory_fact_from_user_confirmation() -> None:
    items = [
        _make_evidence("e1", SourceType.USER_CONFIRMATION, EvidenceStrength.STRONG),
    ]
    digest = build_evidence_digest(items)
    factory = ClaimFactory(digest)

    label, review = factory.evidence_label_for_claim(
        desired=ClaimLabel.FACT,
        evidence_ids=["e1"],
    )
    assert label is ClaimLabel.FACT
    assert review is False


def test_claim_factory_downgrades_non_pending_without_evidence() -> None:
    digest = build_evidence_digest([])
    factory = ClaimFactory(digest)

    label, review = factory.evidence_label_for_claim(
        desired=ClaimLabel.FACT,
        evidence_ids=["nonexistent"],
    )
    assert label is ClaimLabel.PENDING
    assert review is True


def test_claim_factory_weak_evidence_becomes_pending() -> None:
    items = [
        _make_evidence("e1", SourceType.REPO_FILE, EvidenceStrength.WEAK),
    ]
    digest = build_evidence_digest(items)
    factory = ClaimFactory(digest)

    label, review = factory.evidence_label_for_claim(
        desired=ClaimLabel.INFERENCE,
        evidence_ids=["e1"],
    )
    assert label is ClaimLabel.PENDING
    assert review is True


def test_claim_factory_recommendation_always_user_review() -> None:
    items = [
        _make_evidence("e1", SourceType.USER_CONFIRMATION, EvidenceStrength.STRONG),
    ]
    digest = build_evidence_digest(items)
    factory = ClaimFactory(digest)

    label, review = factory.evidence_label_for_claim(
        desired=ClaimLabel.RECOMMENDATION,
        evidence_ids=["e1"],
    )
    # recommendation 的证据可能不足以支撑 strong fact，但至少
    # 降级后应该是 recommendation 并 requires_user_review
    assert review is True


def test_claim_factory_make_keeps_evidence_ids_on_pending() -> None:
    """pending claim 也可以保留 evidence_ids 以展示弱证据。"""
    items = [
        _make_evidence("e1", SourceType.REPO_FILE, EvidenceStrength.WEAK),
    ]
    digest = build_evidence_digest(items)
    factory = ClaimFactory(digest)

    claim = factory.make("某项结论", ClaimLabel.INFERENCE, ["e1"])
    # weak evidence 降级为 pending
    assert claim.label is ClaimLabel.PENDING
    # 但 evidence_ids 应保留
    assert "e1" in claim.evidence_ids
    assert claim.requires_user_review is True


def test_claim_factory_fact_with_mixed_strength() -> None:
    """fact 要求所有 evidence 为 strong + 允许的来源。"""
    items = [
        _make_evidence("e1", SourceType.USER_CONFIRMATION, EvidenceStrength.STRONG),
        _make_evidence("e2", SourceType.REPO_FILE, EvidenceStrength.MEDIUM),
    ]
    digest = build_evidence_digest(items)
    factory = ClaimFactory(digest)

    label, _ = factory.evidence_label_for_claim(
        desired=ClaimLabel.FACT,
        evidence_ids=["e1", "e2"],
    )
    # e2 不是 strong，降级为 inference
    assert label is ClaimLabel.INFERENCE
