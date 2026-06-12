"""1Password 비밀 참조(op://...) 해석기.

os.environ 에 `op://vault/item/field` 형식의 값이 있으면 실제 비밀값으로 치환한다.
인증 수단을 다음 우선순위로 자동 선택한다(헤드리스/SSH 환경을 우선):

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
import logging
import os
import shutil
import subprocess

OP_PREFIX = "op://"

# op read 1건당 타임아웃(초). 생체인증/앱 승인 대기를 고려해 넉넉히 둔다.
_OP_READ_TIMEOUT = 120


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

    # 우선순위 1: op CLI (세션/토큰/앱 연동을 모두 처리, SSH 친화)
    if shutil.which("op"):
        mode = "Service Account 토큰" if has_token else "세션/앱 연동"
        logging.info(
            "🔐 1Password CLI(op read)로 비밀 %d개 resolve 중 (account=%s, %s)...",
            len(targets), account, mode,
        )
        try:
            resolved = _resolve_with_cli(targets, account)
            return _inject(resolved)
        except Exception as e:
            logging.warning("op CLI resolve 실패 → 폴백 시도: %s", e)

    # 우선순위 2: SDK + Service Account 토큰 (op CLI가 없을 때)
    if has_token:
        logging.info("🔐 1Password SDK(Service Account 토큰)로 비밀 %d개 resolve 중...", len(targets))
        resolved = _resolve_with_sdk(targets, account, token=os.environ["OP_SERVICE_ACCOUNT_TOKEN"])
        return _inject(resolved)

    # 우선순위 3: SDK + DesktopAuth (로컬 GUI Touch ID)
    logging.info(
        "🔐 1Password 데스크톱 앱(Touch ID)으로 비밀 %d개 resolve 중 (account=%s)... "
        "필요 시 1Password 앱의 승인을 완료하세요.",
        len(targets), account,
    )
    resolved = _resolve_with_sdk(targets, account, token=None)
    return _inject(resolved)


def _inject(resolved: dict) -> int:
    for key, value in resolved.items():
        os.environ[key] = value
    logging.info("✅ 1Password 비밀 %d개 주입 완료", len(resolved))
    return len(resolved)


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
