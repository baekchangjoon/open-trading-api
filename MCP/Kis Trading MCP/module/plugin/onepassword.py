"""1Password 비밀 참조(op://...) 해석기.

os.environ 에 `op://vault/item/field` 형식의 값이 있으면 실제 비밀값으로 치환한다.
인증 수단을 다음 우선순위로 자동 선택한다(헤드리스/SSH 환경을 우선):

  0. 그날치 캐시              — 오늘 이미 해석한 적이 있으면 op 호출 없이 무인 주입.
                                 op 세션(약 30분)이 만료돼도 그날 안의 재기동은 성공한다.
                                 (하단 "그날치 시크릿 캐시" 섹션 참조)
  1. `op` CLI (op read)        — OP_SESSION_* 세션 / Service Account 토큰 / 앱 연동을
                                 모두 처리. SSH에서 `eval $(op signin)` 후 동작하며,
                                 OP_SERVICE_ACCOUNT_TOKEN 이 있으면 그걸로 무인 동작한다.
  2. SDK + Service Account 토큰 — op CLI가 없고 OP_SERVICE_ACCOUNT_TOKEN 만 있을 때.
  3. SDK + DesktopAuth         — 로컬 GUI Touch ID 폴백.

SSH(헤드리스)에서는 Touch ID GUI 승인을 받을 수 없으므로 1번(op CLI 세션)이 필요하다.
이때 데스크톱 앱 연동(생체인증) 모드는 비밀번호 로그인을 막으므로
`OP_BIOMETRIC_UNLOCK_ENABLED=false` 로 끈 뒤
`eval $(op signin --account <계정>)` 으로 마스터 비밀번호를 한 번 입력해 OP_SESSION_*
세션을 만들고, 그 세션을 물려받은 프로세스로 서버를 기동한다. op read 도 같은 env 를
상속해 세션을 쓴다. (repo의 scripts/ssh-start.sh 런처가 이 과정을 자동화한다)

평문 .env 값(op:// 아님)은 그대로 두므로 1Password 미사용 환경과 완전히 하위호환된다.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from datetime import datetime

OP_PREFIX = "op://"

# op read 1건당 타임아웃(초). 생체인증/앱 승인 대기를 고려해 넉넉히 둔다.
_OP_READ_TIMEOUT = 120

# ── 그날치 시크릿 캐시 ────────────────────────────────────────────────────────
# op CLI 세션은 30분이면 만료된다. ssh-start.sh 로 아침에 비밀번호를 한 번 입력해
# 시크릿을 해석한 뒤, 낮에 `/mcp` 재연결(=서버 재기동)하면 세션이 만료돼 op read 가
# 실패하고 서버가 못 떠서 -32000 이 난다. KIS 키/토큰은 하루 유효하므로, 첫 해석 결과를
# "그날치" 캐시에 저장해 이후 부팅은 op 호출 없이 무인 주입한다(하루 1회 입력이면 충분).
#
# 캐시는 해석된 비밀 평문을 담으므로 레포 밖의 사용자 캐시 디렉토리에 0600 으로 둔다.
# KIS_OP_CACHE=off 로 끌 수 있고, KIS_OP_CACHE_DIR 로 위치를 바꿀 수 있다.
_CACHE_DISABLED_VALUES = {"0", "off", "false", "no"}


def _cache_enabled() -> bool:
    return os.getenv("KIS_OP_CACHE", "on").strip().lower() not in _CACHE_DISABLED_VALUES


def _cache_dir() -> str:
    return os.getenv("KIS_OP_CACHE_DIR") or os.path.join(
        os.path.expanduser("~"), ".cache", "kis-mcp"
    )


def _day_stamp() -> str:
    return datetime.now().strftime("%Y%m%d")


def _env_label() -> str:
    # 서버 기동 ENV(paper/prod) 기준으로 캐시를 분리한다. 없으면 default.
    return (os.getenv("ENV") or os.getenv("KIS_TOKEN_ENV") or "default").strip() or "default"


def _cache_prefix() -> str:
    return f"secrets_{_env_label()}_"


def _cache_file(day: str = "") -> str:
    day = day or _day_stamp()
    return os.path.join(_cache_dir(), f"{_cache_prefix()}{day}.json")


def _load_cache(target_keys, day: str = ""):
    """오늘치 캐시가 target_keys 를 모두 포함하면 그 부분집합 dict 를, 아니면 None 반환."""
    path = _cache_file(day)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    keys = list(target_keys)
    if not set(keys).issubset(data.keys()):
        return None
    return {k: data[k] for k in keys}


def _write_cache(resolved: dict, day: str = "") -> None:
    """해석된 비밀을 그날치 캐시에 0600 으로 원자적 기록하고 과거 날짜 파일을 정리."""
    if not resolved:
        return
    directory = _cache_dir()
    try:
        os.makedirs(directory, mode=0o700, exist_ok=True)
        os.chmod(directory, 0o700)  # 캐시 루트만 보정(상위 경로 권한은 보장하지 않음)
        path = _cache_file(day)
        tmp = path + ".tmp"
        # 심볼릭링크 선점/TOCTOU 방어: 기존 tmp 잔재를 지우고 O_EXCL|O_NOFOLLOW 로
        # 새 파일을 0600 으로만 생성한다(평문 비밀이므로 임의 경로 유도를 막는다).
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(tmp, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(resolved, f, ensure_ascii=False)
        os.replace(tmp, path)
        os.chmod(path, 0o600)
        _cleanup_old_cache(keep_day=day or _day_stamp())
    except OSError as e:
        logging.warning("시크릿 캐시 기록 실패(무시하고 진행): %s", e)


def _cleanup_old_cache(keep_day: str) -> None:
    directory = _cache_dir()
    prefix = _cache_prefix()
    try:
        for name in os.listdir(directory):
            if name.startswith(prefix) and name.endswith(".json") and keep_day not in name:
                try:
                    os.remove(os.path.join(directory, name))
                except OSError:
                    pass
    except OSError:
        pass


def resolve_op_references() -> int:
    """os.environ 의 op:// 참조를 1Password 실제 값으로 치환.

    Returns:
        int: 치환한 환경변수 개수 (0이면 1Password 미사용 → 인증 시도조차 안 함)
    """
    targets = {
        k: v
        for k, v in os.environ.items()
        if isinstance(v, str) and v.startswith(OP_PREFIX)
    }
    if not targets:
        return 0

    account = os.getenv("OP_ACCOUNT", "my.1password.com")
    has_token = bool(os.getenv("OP_SERVICE_ACCOUNT_TOKEN"))

    # 우선순위 0: 그날치 캐시 — op 호출 없이 무인 주입(세션 만료와 무관).
    #   아침에 ssh-start.sh 로 한 번 해석해 두면 낮의 `/mcp` 재연결도 캐시로 성공한다.
    if _cache_enabled():
        cached = _load_cache(targets.keys())
        if cached is not None:
            logging.info(
                "🗄️  1Password 시크릿 그날치 캐시 사용 (%d개, op 호출 생략)", len(cached)
            )
            return _inject(cached)

    # 우선순위 1: op CLI (세션/토큰/앱 연동을 모두 처리, SSH 친화)
    if shutil.which("op"):
        mode = "Service Account 토큰" if has_token else "세션/앱 연동"
        logging.info(
            "🔐 1Password CLI(op read)로 비밀 %d개 resolve 중 (account=%s, %s)...",
            len(targets), account, mode,
        )
        try:
            resolved = _resolve_with_cli(targets, account)
            return _inject_and_cache(resolved)
        except Exception as e:
            logging.warning("op CLI resolve 실패 → 폴백 시도: %s", e)

    # 우선순위 2: SDK + Service Account 토큰 (op CLI가 없을 때)
    if has_token:
        logging.info("🔐 1Password SDK(Service Account 토큰)로 비밀 %d개 resolve 중...", len(targets))
        resolved = _resolve_with_sdk(targets, account, token=os.environ["OP_SERVICE_ACCOUNT_TOKEN"])
        return _inject_and_cache(resolved)

    # 우선순위 3: SDK + DesktopAuth (로컬 GUI Touch ID)
    logging.info(
        "🔐 1Password 데스크톱 앱(Touch ID)으로 비밀 %d개 resolve 중 (account=%s)... "
        "필요 시 1Password 앱의 승인을 완료하세요.",
        len(targets), account,
    )
    resolved = _resolve_with_sdk(targets, account, token=None)
    return _inject_and_cache(resolved)


def _inject(resolved: dict) -> int:
    for key, value in resolved.items():
        os.environ[key] = value
    logging.info("✅ 1Password 비밀 %d개 주입 완료", len(resolved))
    return len(resolved)


def _inject_and_cache(resolved: dict) -> int:
    """주입 후, 캐시가 켜져 있으면 그날치 캐시에 기록한다."""
    n = _inject(resolved)
    if _cache_enabled():
        _write_cache(resolved)
    return n


def _resolve_with_cli(targets: dict, account: str) -> dict:
    """`op read` 로 각 참조를 해석. 계정은 상속된 OP_ACCOUNT 환경변수로 자동 인식된다.

    세션/토큰이 없으면 op가 비대화형(non-TTY)에서 즉시 실패하므로 행이 걸리지 않고
    상위에서 DesktopAuth 폴백으로 넘어간다.
    """
    resolved = {}
    for key, ref in targets.items():
        proc = subprocess.run(
            ["op", "read", "--no-newline", ref],
            capture_output=True,
            text=True,
            timeout=_OP_READ_TIMEOUT,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()
            raise RuntimeError(
                f"op read 실패 ({ref}): {err} | "
                f"SSH 세션이라면 먼저 `eval $(op signin --account {account})` 로 로그인하세요."
            )
        resolved[key] = proc.stdout
    return resolved


def _resolve_with_sdk(targets: dict, account: str, token) -> dict:
    """1Password SDK 로 해석. token 이 있으면 Service Account, 없으면 DesktopAuth."""
    try:
        from onepassword.client import Client, DesktopAuth
    except ImportError as e:
        raise RuntimeError(
            "op:// 참조가 있으나 onepassword-sdk 를 불러올 수 없습니다. "
            "`uv add onepassword-sdk` 후 다시 시도하세요."
        ) from e

    integration = os.getenv("OP_INTEGRATION_NAME", "KIS Trading MCP")

    async def _resolve() -> dict:
        auth = token if token else DesktopAuth(account_name=account)
        client = await Client.authenticate(
            auth=auth,
            integration_name=integration,
            integration_version="v1.0.0",
        )
        out = {}
        for key, ref in targets.items():
            out[key] = await client.secrets.resolve(ref)
        return out

    return asyncio.run(_resolve())
