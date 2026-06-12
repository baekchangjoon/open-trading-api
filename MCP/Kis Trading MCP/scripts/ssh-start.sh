#!/usr/bin/env bash
#
# SSH/헤드리스 환경에서 kis-trade-mcp 를 쓰기 위한 런처.
#
# 동작:
#   1. 1Password CLI 세션이 유효한지 확인하고, 없으면 `op signin` 으로 마스터
#      비밀번호를 1회 입력받아 OP_SESSION_* 세션을 만든다.
#   2. 그 세션 환경을 물려받은 채 Claude Code 를 기동한다.
#      → Claude Code 가 띄우는 kis-trade-mcp 서버가 부팅 시 op:// 참조를
#        op read 로 해석한다(생체인증 불필요).
#
# 1Password 비밀은 "서버 기동 순간"에만 필요하므로, 세션이 그 이후 만료돼도
# 거래 동작에는 영향이 없다. 다음 서버 재기동 때 이 스크립트를 다시 실행하면 된다.
#
# 사용법:
#   ./scripts/ssh-start.sh            # 기본 계정(OP_ACCOUNT 또는 my)으로 로그인 후 claude 기동
#   OP_ACCOUNT=my ./scripts/ssh-start.sh
#   ./scripts/ssh-start.sh --resume   # claude 에 그대로 전달되는 인자
#
# 편의를 위해 alias 등록도 가능:
#   alias kis='/path/to/MCP/Kis\ Trading\ MCP/scripts/ssh-start.sh'

set -euo pipefail

OP_ACCOUNT="${OP_ACCOUNT:-my}"

# 데스크톱 앱 연동(생체인증) 모드를 끄고 standalone 비밀번호 세션을 쓴다.
# 헤드리스/SSH 에는 GUI Touch ID 가 없으므로, 이게 없으면 `op signin` 이
# "operation not supported by device" 로 실패한다. 이 env 는 op CLI 가 인식하며,
# exec 로 물려받는 Claude Code → kis-trade-mcp 의 op read 도 세션을 쓰게 한다.
export OP_BIOMETRIC_UNLOCK_ENABLED=false

if ! command -v op >/dev/null 2>&1; then
  echo "❌ 1Password CLI(op)가 설치되어 있지 않습니다. https://developer.1password.com/docs/cli/get-started/" >&2
  exit 1
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "❌ Claude Code(claude) 가 PATH 에 없습니다." >&2
  exit 1
fi

# 이미 유효한 세션/토큰이 있으면 재로그인 생략
if op whoami --account "$OP_ACCOUNT" >/dev/null 2>&1; then
  echo "✅ 1Password 세션 유효 (account=$OP_ACCOUNT) — 재로그인 생략"
else
  echo "🔐 1Password 로그인 (account=$OP_ACCOUNT) — 마스터 비밀번호를 입력하세요."
  eval "$(op signin --account "$OP_ACCOUNT")"
fi

echo "🚀 Claude Code 기동..."
exec claude "$@"
