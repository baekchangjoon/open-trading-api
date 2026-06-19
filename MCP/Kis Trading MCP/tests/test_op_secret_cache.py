# -*- coding: utf-8 -*-
"""
onepassword.resolve_op_references() 의 "그날치 시크릿 캐시" 동작 테스트.

배경: MCP 서버는 부팅 시 op:// 시크릿을 1Password 로 해석한다. 그런데 op CLI 세션은
30분이면 만료되므로, ssh-start.sh 로 아침에 로그인한 뒤 낮에 `/mcp` 재연결(=서버 재기동)
하면 세션 만료로 op read 가 실패하고 서버가 못 떠서 -32000 이 난다.

해법: 첫 해석 성공 시 결과를 "그날치" 캐시(0600)에 저장하고, 이후 부팅은 캐시가 있으면
op 호출 없이 무인 주입한다. KIS 키가 하루 유효하므로 하루 1회 비밀번호 입력이면 충분.

이 테스트는 stdlib 만으로 onepassword.py 를 importlib 로 직접 로드해(패키지 __init__ 의
무거운 의존성 회피) 캐시 함수와 통합 동작을 검증한다.
"""
import importlib.util
import json
import os
import stat
import tempfile

OP_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "module", "plugin", "onepassword.py")
)


def _load_module():
    spec = importlib.util.spec_from_file_location("op_under_test", OP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fresh_env(tmpdir):
    os.environ["KIS_OP_CACHE_DIR"] = tmpdir
    os.environ["ENV"] = "paper"
    os.environ.pop("KIS_OP_CACHE", None)
    # op:// 타겟만 남기고 이전 주입값 정리
    for k in ("KIS_APP_KEY", "KIS_APP_SECRET"):
        os.environ.pop(k, None)


def test_write_then_load_roundtrip_with_0600_perms():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        day = op._day_stamp()
        resolved = {"KIS_APP_KEY": "appkey-xyz", "KIS_APP_SECRET": "secret-123"}
        op._write_cache(resolved, day=day)

        path = op._cache_file(day=day)
        assert os.path.isfile(path), "캐시 파일이 생성되어야 함"
        mode = stat.S_IMODE(os.stat(path).st_mode)
        assert mode == 0o600, f"캐시 파일 권한은 0600 이어야 함, 실제={oct(mode)}"

        loaded = op._load_cache(resolved.keys(), day=day)
        assert loaded == resolved, f"라운드트립 불일치: {loaded}"


def test_load_returns_none_when_a_target_key_missing():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        day = op._day_stamp()
        op._write_cache({"KIS_APP_KEY": "k"}, day=day)
        # 두 키를 요구하지만 캐시엔 하나뿐 → None (op 재해석 유도)
        assert op._load_cache(["KIS_APP_KEY", "KIS_APP_SECRET"], day=day) is None


def test_load_ignores_other_day_cache():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        op._write_cache({"KIS_APP_KEY": "k"}, day="20200101")
        # 오늘 캐시는 없음 → None
        assert op._load_cache(["KIS_APP_KEY"], day=op._day_stamp()) is None


def test_write_cleans_up_old_day_files():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        old = op._cache_file(day="20200101")
        os.makedirs(d, exist_ok=True)
        with open(old, "w") as f:
            json.dump({"KIS_APP_KEY": "old"}, f)
        # 오늘치 기록 시 과거 날짜 파일은 정리되어야 함
        op._write_cache({"KIS_APP_KEY": "new"}, day=op._day_stamp())
        assert not os.path.isfile(old), "과거 날짜 캐시는 정리되어야 함"


def test_resolve_uses_cache_and_skips_op():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        day = op._day_stamp()
        op._write_cache({"KIS_APP_KEY": "cached-key", "KIS_APP_SECRET": "cached-sec"}, day=day)

        # op CLI 가 호출되면 실패시켜, 캐시 히트로 op 를 건드리지 않음을 보장
        def _boom(*a, **k):
            raise AssertionError("캐시 히트 시 op read 가 호출되면 안 됨")
        op.subprocess.run = _boom

        os.environ["KIS_APP_KEY"] = "op://Private/kis-trading/KIS_APP_KEY"
        os.environ["KIS_APP_SECRET"] = "op://Private/kis-trading/KIS_APP_SECRET"

        n = op.resolve_op_references()
        assert n == 2
        assert os.environ["KIS_APP_KEY"] == "cached-key"
        assert os.environ["KIS_APP_SECRET"] == "cached-sec"


def test_resolve_writes_cache_after_op_resolution():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        os.environ["KIS_APP_KEY"] = "op://Private/kis-trading/KIS_APP_KEY"

        # op CLI 해석을 가짜로 성공시키고, 그 결과가 캐시에 기록되는지 본다
        op.shutil.which = lambda _name: "/usr/bin/op"
        op._resolve_with_cli = lambda targets, account: {k: "resolved-" + k for k in targets}

        n = op.resolve_op_references()
        assert n == 1
        assert os.environ["KIS_APP_KEY"] == "resolved-KIS_APP_KEY"

        cached = op._load_cache(["KIS_APP_KEY"], day=op._day_stamp())
        assert cached == {"KIS_APP_KEY": "resolved-KIS_APP_KEY"}, "op 해석 후 캐시 기록 누락"


def test_cache_disabled_skips_cache_read():
    op = _load_module()
    with tempfile.TemporaryDirectory() as d:
        _fresh_env(d)
        os.environ["KIS_OP_CACHE"] = "off"
        day = op._day_stamp()
        op._write_cache({"KIS_APP_KEY": "should-not-be-used"}, day=day)

        # 캐시 비활성 → 캐시를 읽지 않고 op 경로로 가야 한다
        op.shutil.which = lambda _name: "/usr/bin/op"
        op._resolve_with_cli = lambda targets, account: {k: "fresh-" + k for k in targets}
        os.environ["KIS_APP_KEY"] = "op://Private/kis-trading/KIS_APP_KEY"

        n = op.resolve_op_references()
        assert n == 1
        assert os.environ["KIS_APP_KEY"] == "fresh-KIS_APP_KEY", "비활성인데 캐시가 사용됨"


if __name__ == "__main__":
    test_write_then_load_roundtrip_with_0600_perms()
    test_load_returns_none_when_a_target_key_missing()
    test_load_ignores_other_day_cache()
    test_write_cleans_up_old_day_files()
    test_resolve_uses_cache_and_skips_op()
    test_resolve_writes_cache_after_op_resolution()
    test_cache_disabled_skips_cache_read()
    print("PASS")
