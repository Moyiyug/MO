"""从 RepoDigest 构建 RepoCard（PRD F-004）。"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

logger = logging.getLogger("mo_api.repo_card")

from ..adapters.model_gateway.gateway import ModelGateway
from ..models.enums import ClaimLabel, EvidenceStrength, SourceType
from ..models.evidence import EvidenceItem
from ..models.repo import RepoCard, RepoDigest
from ..services.evidence_service import EvidenceService

_EXT_LANG: dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".rb": "Ruby",
    ".php": "PHP",
}


def _repo_name(repo_url: str) -> str:
    path = urlparse(repo_url).path.strip("/")
    parts = path.split("/")
    return parts[-1] if parts else repo_url


def _find_content(content: dict[str, str], *names: str) -> tuple[str | None, str | None]:
    lowered = {k.lower(): k for k in content}
    for name in names:
        key = lowered.get(name.lower())
        if key is not None:
            return key, content[key]
    return None, None


def _parse_requirements(text: str) -> list[str]:
    deps: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        deps.append(line.split(";", 1)[0].strip())
    return deps


def _parse_pyproject(text: str) -> list[str]:
    deps: list[str] = []
    try:
        import tomllib

        data = tomllib.loads(text)
        project = data.get("project", {})
        deps.extend(project.get("dependencies") or [])
        optional = project.get("optional-dependencies") or {}
        for group in optional.values():
            deps.extend(group or [])
    except Exception:
        for match in re.finditer(r'["\']([^"\']+)["\']\s*,?', text):
            val = match.group(1)
            if any(c in val for c in ("==", ">=", "~=")):
                deps.append(val)
    return deps


def _parse_package_json(text: str) -> list[str]:
    deps: list[str] = []
    try:
        data = json.loads(text)
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            section_deps = data.get(section) or {}
            for name, spec in section_deps.items():
                deps.append(f"{name}@{spec}" if spec else name)
    except json.JSONDecodeError:
        pass
    return deps


def _detect_docs_paths(content: dict[str, str]) -> list[str]:
    docs: list[str] = []
    for path in content:
        lower = path.lower()
        if lower.startswith("docs/") or lower in {"readme.md", "readme.rst", "readme"}:
            docs.append(path)
        elif "/docs/" in lower:
            docs.append(path)
    return sorted(set(docs))[:20]


def _detect_test_paths(content: dict[str, str]) -> list[str]:
    tests: list[str] = []
    for path in content:
        lower = path.lower()
        if lower.startswith("test") or "/test" in lower or lower.endswith("_test.py"):
            tests.append(path)
    return sorted(set(tests))[:20]


def _derive_test_commands(
    content: dict[str, str], test_paths: list[str]
) -> list[str]:
    """从包清单推断可执行的测试命令（F-008）。

    返回真实命令字符串（如 "npm test"、"python -m pytest"），而非文件路径。
    """
    commands: list[str] = []

    # 检查 package.json（npm/Node.js 项目）
    _, pkg_text = _find_content(content, "package.json")
    if pkg_text:
        try:
            pkg = json.loads(pkg_text)
            scripts = pkg.get("scripts") or {}
            if "test" in scripts:
                commands.append("npm test")
        except (json.JSONDecodeError, TypeError):
            pass

    # 检查 Python 项目清单
    _, py_text = _find_content(content, "pyproject.toml")
    _, req_text = _find_content(content, "requirements.txt")
    _, setup_text = _find_content(content, "setup.py")
    if py_text or req_text or setup_text:
        if test_paths:
            commands.append("python -m pytest")
        else:
            commands.append("python -m pytest")

    # 无清单但有测试路径：保守回退
    if not commands and test_paths:
        commands.append("python -m pytest")

    return commands[:5]


def _primary_language(content: dict[str, str]) -> str | None:
    counts: dict[str, int] = {}
    for path in content:
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        lang = _EXT_LANG.get(ext)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    lower_paths = {path.lower() for path in content}
    if lower_paths & {"pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"}:
        return "Python"
    if "package.json" in lower_paths:
        return "JavaScript"
    return None


def _primary_language_label(content: dict[str, str], language: str) -> ClaimLabel:
    for path in content:
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if _EXT_LANG.get(ext) == language:
            return ClaimLabel.FACT
    return ClaimLabel.INFERENCE


def _make_evidence(
    *,
    task_id: str,
    source_uri: str,
    locator: str,
    summary: str,
) -> EvidenceItem:
    return EvidenceItem(
        id=uuid.uuid4().hex,
        task_id=task_id,
        source_type=SourceType.REPO_FILE,
        source_uri=source_uri,
        locator=locator,
        quote_or_summary=summary[:2000],
        strength=EvidenceStrength.STRONG,
        created_at=datetime.now(timezone.utc),
    )


def _parse_jsonish(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        logger.debug("JSON parse failed for LLM output: %s", text[:100])
    result: dict = {}
    for key in ("project_type", "entrypoints", "risks"):
        if key == "entrypoints" or key == "risks":
            match = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', text, re.DOTALL)
            if match:
                items = re.findall(r'"([^"]+)"', match.group(1))
                result[key] = items
        else:
            match = re.search(rf'"{key}"\s*:\s*"([^"]+)"', text)
            if match:
                result[key] = match.group(1)
    return result


def _infer_project_type(digest: RepoDigest) -> str | None:
    content_sample = "\n".join(list(digest.content.values())[:4])
    text = f"{digest.source_uri}\n{digest.summary}\n{digest.tree}\n{content_sample}".lower()
    if any(
        token in text
        for token in ("rag", "retrieval", "llm", "agent", "llama-index")
    ):
        return "LLM/RAG application framework"
    if any(token in text for token in ("library", "framework", "package")):
        return "software library/framework"
    if "api" in text:
        return "API/service project"
    return None


def _normalize_project_type(
    project_type: str | None,
    digest: RepoDigest,
) -> str | None:
    inferred = _infer_project_type(digest)
    current = (project_type or "").strip()
    if not current:
        return inferred
    if current.lower() in {
        "python",
        "python project",
        "yes",
        "unknown",
        "repository",
        "repo",
        "library",
        "framework",
        "software",
    } and inferred:
        return inferred
    return current


def _infer_entrypoints(content: dict[str, str]) -> list[str]:
    candidates: list[str] = []
    for path in content:
        lower = path.lower()
        if lower.endswith("__init__.py") and "test" not in lower:
            candidates.append(path)
        elif lower in {"main.py", "app.py", "cli.py"}:
            candidates.append(path)
        elif lower.endswith("/main.py") or lower.endswith("/cli.py"):
            candidates.append(path)
    return sorted(dict.fromkeys(candidates))[:10]


async def build_repo_card(
    task_id: str,
    digest: RepoDigest,
    gateway: ModelGateway,
    evidence_service: EvidenceService,
) -> RepoCard:
    """构建 RepoCard：确定性字段 + LLM 推断字段。"""
    content = digest.content
    evidence_ids: list[str] = []
    field_labels: dict[str, str] = {}

    dependencies: list[str] = []
    license_value: str | None = None
    docs_paths = _detect_docs_paths(content)
    test_paths = _detect_test_paths(content)

    license_path, license_text = _find_content(content, "LICENSE", "LICENSE.md", "LICENSE.txt")
    if license_text:
        license_value = license_text.splitlines()[0][:200]
        eid = evidence_service.add(
            _make_evidence(
                task_id=task_id,
                source_uri=digest.source_uri,
                locator=license_path or "LICENSE",
                summary=f"License header: {license_value}",
            )
        )
        evidence_ids.append(eid)
        field_labels["license"] = ClaimLabel.FACT.value

    req_path, req_text = _find_content(content, "requirements.txt")
    if req_text:
        deps = _parse_requirements(req_text)
        dependencies.extend(deps)
        eid = evidence_service.add(
            _make_evidence(
                task_id=task_id,
                source_uri=digest.source_uri,
                locator=req_path or "requirements.txt",
                summary=f"requirements.txt: {len(deps)} dependencies",
            )
        )
        evidence_ids.append(eid)
        field_labels["dependencies"] = ClaimLabel.FACT.value

    py_path, py_text = _find_content(content, "pyproject.toml")
    if py_text:
        deps = _parse_pyproject(py_text)
        dependencies.extend(deps)
        eid = evidence_service.add(
            _make_evidence(
                task_id=task_id,
                source_uri=digest.source_uri,
                locator=py_path or "pyproject.toml",
                summary=f"pyproject.toml: {len(deps)} dependencies",
            )
        )
        evidence_ids.append(eid)
        if "dependencies" not in field_labels:
            field_labels["dependencies"] = ClaimLabel.FACT.value

    pkg_path, pkg_text = _find_content(content, "package.json")
    if pkg_text:
        deps = _parse_package_json(pkg_text)
        dependencies.extend(deps)
        eid = evidence_service.add(
            _make_evidence(
                task_id=task_id,
                source_uri=digest.source_uri,
                locator=pkg_path or "package.json",
                summary=f"package.json: {len(deps)} dependencies",
            )
        )
        evidence_ids.append(eid)
        if "dependencies" not in field_labels:
            field_labels["dependencies"] = ClaimLabel.FACT.value

    if docs_paths:
        field_labels["docs_paths"] = ClaimLabel.FACT.value
        for dp in docs_paths[:10]:
            eid = evidence_service.add(
                _make_evidence(
                    task_id=task_id,
                    source_uri=digest.source_uri,
                    locator=dp,
                    summary=f"Documentation path: {dp}",
                )
            )
            evidence_ids.append(eid)
    if test_paths:
        field_labels["test_commands"] = ClaimLabel.FACT.value
        for tp in test_paths[:10]:
            eid = evidence_service.add(
                _make_evidence(
                    task_id=task_id,
                    source_uri=digest.source_uri,
                    locator=tp,
                    summary=f"Test path: {tp}",
                )
            )
            evidence_ids.append(eid)

    primary_language = _primary_language(content)
    if primary_language:
        language_label = _primary_language_label(content, primary_language)
        field_labels["primary_language"] = language_label.value
        eid = evidence_service.add(
            _make_evidence(
                task_id=task_id,
                source_uri=digest.source_uri,
                locator="<file-tree>",
                summary=f"Primary language: {primary_language}",
            )
        )
        evidence_ids.append(eid)

    project_type: str | None = None
    entrypoints: list[str] = []
    risks: list[str] = []

    profile = gateway.select(need_reasoning=True, need_json=True)
    prompt = (
        "Analyze this repository digest and respond with JSON only:\n"
        '{"project_type": "...", "entrypoints": ["..."], "risks": ["..."]}\n\n'
        f"Summary:\n{digest.summary[:4000]}\n\nTree:\n{digest.tree[:4000]}"
    )
    try:
        raw = await gateway.complete(
            profile,
            [{"role": "user", "content": prompt}],
            max_tokens=512,
            json_mode=True,
        )
        parsed = _parse_jsonish(raw)
        project_type = parsed.get("project_type")
        entrypoints = list(parsed.get("entrypoints") or [])
        risks = list(parsed.get("risks") or [])
        field_labels["project_type"] = ClaimLabel.INFERENCE.value
        field_labels["entrypoints"] = ClaimLabel.INFERENCE.value
        field_labels["risks"] = ClaimLabel.INFERENCE.value
    except Exception as exc:
        logger.warning("LLM inference failed for repo_card: %s", exc)
        field_labels["project_type"] = ClaimLabel.PENDING.value
        field_labels["entrypoints"] = ClaimLabel.PENDING.value
        field_labels["risks"] = ClaimLabel.PENDING.value

    normalized_project_type = _normalize_project_type(project_type, digest)
    if normalized_project_type != project_type:
        project_type = normalized_project_type
        if project_type:
            field_labels["project_type"] = ClaimLabel.INFERENCE.value
    if not entrypoints:
        entrypoints = _infer_entrypoints(content)
        if entrypoints:
            field_labels["entrypoints"] = ClaimLabel.INFERENCE.value

    return RepoCard(
        id=uuid.uuid4().hex,
        task_id=task_id,
        repo_url=digest.source_uri,
        repo_name=_repo_name(digest.source_uri),
        summary=digest.summary[:4000],
        primary_language=primary_language,
        project_type=project_type,
        dependencies=sorted(set(dependencies))[:100],
        entrypoints=entrypoints[:20],
        test_commands=_derive_test_commands(content, test_paths),
        docs_paths=docs_paths,
        license=license_value,
        risks=risks[:20],
        evidence_ids=evidence_ids,
        field_labels=field_labels,
    )
