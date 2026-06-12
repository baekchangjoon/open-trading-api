"""1Password 비밀 참조(op://...) 해석기.

os.environ 에 `op://vault/item/field` 형식의 값이 있으면, 1Password 데스크톱 앱
인증(DesktopAuth)을 통해 실제 비밀값으로 치환한다. Service Account 토큰이 필요 없고,
1Password 앱이 Touch ID 등 GUI 승인 프롬프트를 띄운다(헤드리스/비대화형 프로세스에서도 동작).

평문 .env 값(op:// 아님)은 그대로 두므로, 1Password를 쓰지 않는 환경(예: ENV=live)과
완전히 하위호환된다.
"""

import asyncio
import logging
import os

OP_PREFIX = "op://"


def resolve_op_references() -> int:
    """os.environ 의 op:// 참조를 1Password 실제 값으로 치환.

    Returns:
        int: 치환한 환경변수 개수 (0이면 1Password 미사용 → SDK 호출조차 안 함)
    """
    targets = {
        k: v
        for k, v in os.environ.items()
        if isinstance(v, str) and v.startswith(OP_PREFIX)
    }
    if not targets:
        return 0

    try:
        from onepassword.client import Client, DesktopAuth
    except ImportError as e:
        logging.error(
            "op:// 참조가 있으나 onepassword-sdk 를 불러올 수 없습니다. "
            "`uv add onepassword-sdk` 후 다시 시도하세요. (%s)",
            e,
        )
        raise

    account = os.getenv("OP_ACCOUNT", "my.1password.com")
    integration = os.getenv("OP_INTEGRATION_NAME", "KIS Trading MCP")

    async def _resolve() -> dict:
        client = await Client.authenticate(
            auth=DesktopAuth(account_name=account),
            integration_name=integration,
            integration_version="v1.0.0",
        )
        resolved = {}
        for key, ref in targets.items():
            resolved[key] = await client.secrets.resolve(ref)
        return resolved

    logging.info(
        "🔐 1Password에서 비밀 참조 %d개 resolve 중 (account=%s)... "
        "필요 시 1Password 앱의 승인(Touch ID)을 완료하세요.",
        len(targets),
        account,
    )
    resolved = asyncio.run(_resolve())
    for key, value in resolved.items():
        os.environ[key] = value
    logging.info("✅ 1Password 비밀 %d개 주입 완료", len(resolved))
    return len(resolved)
