#!/usr/bin/env python3
"""
PreToolUse 훅: kis-trade-mcp 도구의 주문(쓰기) 동작만 권한 요청.

kis-trade-mcp 는 클래스당 MCP 도구 1개(domestic_stock, overseas_stock 등)만
노출하고, 조회/주문 구분은 `api_type` 인자로 한다. Claude Code 의 allow/ask
규칙은 '도구 이름' 단위라 인자(api_type)를 못 본다. 그래서 이 훅이 api_type 을
직접 보고 결정한다.

  - 조회(READ)  api_type  -> permissionDecision "allow"  (프롬프트 없이 통과)
  - 주문(WRITE) api_type  -> permissionDecision "ask"    (사용자 승인 요청)
  - 판단 불가              -> "ask" (fail-safe: 의심되면 물어본다)

stdin 으로 PreToolUse 이벤트 JSON 을 받고, stdout 으로 결정 JSON 을 낸다.
"""
import json
import sys

SERVER_PREFIX = "mcp__kis-trade-mcp__"

# 도구별 '주문/정정/취소/예약접수' = 쓰기 api_type (현재 config 기준, 명시적 권위 목록)
EXPLICIT_WRITE = {
    "domestic_stock": {
        "order_cash", "order_credit", "order_rvsecncl",
        "order_resv", "order_resv_rvsecncl",
    },
    "domestic_bond": {"buy", "sell", "order_rvsecncl"},
    "domestic_futureoption": {"order", "order_rvsecncl"},
    "overseas_stock": {
        "order", "order_rvsecncl", "daytime_order", "daytime_order_rvsecncl",
        "order_resv", "order_resv_ccnl",
    },
    "overseas_futureoption": {"order", "order_rvsecncl"},
}

# 이름이 order/buy/sell 처럼 보이지만 실제론 '조회'인 api_type (오탐 방지용 화이트리스트)
KNOWN_READ_ORDERLIKE = {
    "domestic_stock": {"order_resv_ccnl"},          # 주식예약주문조회
    "overseas_stock": {"order_resv_list", "algo_ordno"},  # 예약주문조회 / 주문번호조회
}


def is_write(tool: str, api_type: str) -> bool:
    if api_type in EXPLICIT_WRITE.get(tool, set()):
        return True
    if api_type in KNOWN_READ_ORDERLIKE.get(tool, set()):
        return False
    # fail-safe 일반 규칙: 새 주문 API 가 추가돼도 잡아낸다.
    if api_type.startswith("order") or api_type.startswith("daytime_order") \
            or api_type in ("buy", "sell"):
        return True
    return False


def decide(tool_name: str, tool_input: dict):
    tool = tool_name[len(SERVER_PREFIX):] if tool_name.startswith(SERVER_PREFIX) else tool_name
    api_type = (tool_input or {}).get("api_type")

    if not api_type:
        return "ask", f"{tool}: api_type 을 확인할 수 없어 안전을 위해 승인을 요청합니다."
    if is_write(tool, api_type):
        return "ask", f"주문/정정/취소 동작입니다 ({tool} · api_type={api_type}). 실행 전 승인이 필요합니다."
    return "allow", f"조회 동작입니다 ({tool} · api_type={api_type})."


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        # 입력 파싱 실패 시 막지 않고 통과(다른 안전장치에 위임)
        return

    decision, reason = decide(data.get("tool_name", ""), data.get("tool_input") or {})
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))


if __name__ == "__main__":
    main()
