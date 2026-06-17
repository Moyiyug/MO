"""PreflightService 单元测试（F-005）。

测试执行前检查逻辑：
- check_required_model_profiles: 模型能力 + API 密钥检查
- check_git_available: git 可用性检查
"""

from __future__ import annotations

import pytest

from mo_api.services.preflight_service import PreflightService
from mo_api.adapters.model_gateway.profiles import ModelConfigError


# ── Test Doubles ──────────────────────────────────────────────────────────

class _FakeProfile:
    """最小 profile 桩：满足 PreflightService 访问 .api_key_env 的需求。"""
    id = "fake"
    api_key_env = "FAKE_API_KEY"


class _MockGateway:
    """可控的 ModelGateway 替身。

    - fail_on_select=False: select() 正常返回 _FakeProfile
    - fail_on_select=True: select() 抛出 ModelConfigError
    """

    def __init__(self, fail_on_select: bool = False):
        self.fail_on_select = fail_on_select
        self.select_calls: list[dict] = []

    def select(self, **kwargs):
        self.select_calls.append(kwargs)
        if self.fail_on_select:
            raise ModelConfigError("no matching profile for capabilities")
        return _FakeProfile()


class _MockProfileStore:
    """可控的 ProfileStore 替身。

    - has_key=True: has_api_key() 返回 True
    - has_key=False: has_api_key() 返回 False
    """

    def __init__(self, has_key: bool = True):
        self._has_key = has_key

    def has_api_key(self, profile) -> bool:
        return self._has_key


# ── Tests: check_required_model_profiles ──────────────────────────────────

class TestCheckRequiredModelProfiles:
    """测试 check_required_model_profiles() 的三种路径。"""

    def test_all_ok(self):
        """配置文件可用且 API 密钥已设置 → 返回空错误列表。"""
        gw = _MockGateway()
        store = _MockProfileStore(has_key=True)
        svc = PreflightService(gw, store)

        errors = svc.check_required_model_profiles()

        assert errors == []
        # 两次 check：need_reasoning+need_json 和 need_json only
        assert len(gw.select_calls) == 2
        assert gw.select_calls[0] == {"need_reasoning": True, "need_json": True}
        assert gw.select_calls[1] == {"need_json": True}

    def test_missing_profile(self):
        """select() 抛出 ModelConfigError → 每个 check 产生一个错误。"""
        gw = _MockGateway(fail_on_select=True)
        store = _MockProfileStore(has_key=True)
        svc = PreflightService(gw, store)

        errors = svc.check_required_model_profiles()

        assert len(errors) == 2
        for e in errors:
            assert "缺少能力配置文件" in e

    def test_missing_api_key(self):
        """配置文件存在但 has_api_key() 返回 False → 每个 check 产生一个错误。"""
        gw = _MockGateway(fail_on_select=False)
        store = _MockProfileStore(has_key=False)
        svc = PreflightService(gw, store)

        errors = svc.check_required_model_profiles()

        assert len(errors) == 2
        for e in errors:
            assert "缺少 API 密钥" in e
            assert "FAKE_API_KEY" in e


# ── Tests: check_git_available ────────────────────────────────────────────

@pytest.mark.asyncio
class TestCheckGitAvailable:
    """测试 check_git_available() 的三种路径。

    使用 monkeypatch 替换 subprocess.run 避免真实创建子进程；
    同时 mock shutil.which 控制 git 路径查找。
    """

    async def test_git_available_success(self, monkeypatch):
        """git --version 退出码 0 → 返回 None。"""
        import subprocess

        svc = PreflightService(gateway=None, store=None)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/git")
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=0, stdout=b"git version 2.40.0\n", stderr=b"",
            ),
        )
        result = await svc.check_git_available()
        assert result is None

    async def test_git_not_found(self, monkeypatch):
        """shutil.which 返回 None → 返回含"未找到 git"的错误信息。"""
        svc = PreflightService(gateway=None, store=None)
        monkeypatch.setattr("shutil.which", lambda _: None)
        result = await svc.check_git_available()
        assert result is not None
        assert "未找到 git" in result

    async def test_git_nonzero_exit(self, monkeypatch):
        """git 退出码非零 → 返回含"git 不可用"的错误信息。"""
        import subprocess

        svc = PreflightService(gateway=None, store=None)
        monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/git")
        monkeypatch.setattr(
            "subprocess.run",
            lambda *a, **kw: subprocess.CompletedProcess(
                args=[], returncode=1, stdout=b"", stderr=b"unknown option",
            ),
        )
        result = await svc.check_git_available()
        assert result is not None
        assert "git 不可用" in result
