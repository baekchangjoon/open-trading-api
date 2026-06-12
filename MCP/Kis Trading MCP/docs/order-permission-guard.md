# 주문 권한 가드 (Order Permission Guard)

이 문서는 kis-trade-mcp 에서 **조회는 자동 허용하고 주문(매수/매도/정정/취소/예약접수)만
사용자 승인을 받도록** 하는 안전장치의 설계·구현·향후 계획을 정리한다.

- **현재**: 클라이언트(Claude Code) 측 **PreToolUse 훅** 으로 동작 — *로컬 전용*
- **예정(TODO)**: 서버 측 **env 플래그 가드** 추가 — *배포본 전체에 강제*

---

## 1. 배경 — 왜 단순 권한 규칙으로는 안 되는가

kis-trade-mcp 는 클래스당 MCP 도구를 **1개**만 노출한다(`server.py` 의 `register()`):

```python
mcp_server.tool(self._run, name=self.tool_name, ...)
```

따라서 외부에 보이는 MCP 도구는 8개뿐이다:

```
domestic_stock, domestic_bond, domestic_futureoption,
overseas_stock, overseas_futureoption, elw, etfetn, auth
```

조회냐 주문이냐는 **도구 이름이 아니라 `api_type` 인자**로 갈린다. 예를 들어
`domestic_stock` 하나가 `api_type="inquire_price"`(조회)도 하고
`api_type="order_cash"`(현금 주문)도 한다.

그런데 Claude Code 의 `allow`/`ask`/`deny` 권한 규칙은 **도구 이름 단위**라
인자(`api_type`)를 보지 못한다. `mcp__kis-trade-mcp__domestic_stock` 전체를
허용하거나 막을 수만 있고, "조회는 허용 / 주문만 확인"을 표현할 수 없다.

→ **인자를 들여다보고 판단하는 계층**이 필요하다.

---

## 2. 현재 구현 — 클라이언트 측 PreToolUse 훅

### 파일

| 파일 | 역할 | git |
|---|---|---|
| `.claude/hooks/kis-order-guard.py` | `api_type` 을 보고 조회→`allow` / 주문→`ask` 결정 | tracked 가능 |
| `.claude/settings.local.json` | 훅 등록 + 일반 도구 자동 허용(`acceptEdits`, `Bash`) | **gitignore됨** |

> 경로는 **레포 루트**(`open-trading-api/`) 기준이다. Claude Code 가 그 디렉토리에서
> 실행될 때 훅이 동작한다. MCP 서버 디렉토리(`MCP/Kis Trading MCP/`)와는 별개 계층이다.

### 동작

PreToolUse 훅은 도구 호출이 MCP 서버로 가기 **전에** stdin 으로 이벤트 JSON 을 받고,
stdout 으로 권한 결정을 돌려준다.

```jsonc
// 입력(요지): {"tool_name":"mcp__kis-trade-mcp__domestic_stock",
//             "tool_input":{"api_type":"order_cash","params":{...}}}
// 출력:
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",   // 조회면 "allow"
    "permissionDecisionReason": "주문/정정/취소 동작입니다 ..."
  }
}
```

- **조회 api_type** → `allow` (프롬프트 없이 통과)
- **주문 api_type** → `ask` (사용자 승인 요청)
- **판단 불가**(api_type 누락 등) → `ask` (fail-safe: 의심되면 물어본다)

### 주문(쓰기)으로 분류되는 api_type

도구별 명시 목록(현재 `configs/*.json` 기준):

| 도구 | 주문 api_type |
|---|---|
| `domestic_stock` | `order_cash`, `order_credit`, `order_rvsecncl`, `order_resv`, `order_resv_rvsecncl` |
| `domestic_bond` | `buy`, `sell`, `order_rvsecncl` |
| `domestic_futureoption` | `order`, `order_rvsecncl` |
| `overseas_stock` | `order`, `order_rvsecncl`, `daytime_order`, `daytime_order_rvsecncl`, `order_resv`, `order_resv_ccnl` |
| `overseas_futureoption` | `order`, `order_rvsecncl` |

추가로, 새 주문 API 가 생겨도 잡도록 **fail-safe 일반 규칙**(`order*`/`daytime_order*`/`buy`/`sell`
패턴)을 둔다. 단, 이름은 주문처럼 보이지만 실제론 조회인 항목은 화이트리스트로 예외 처리한다:

- `domestic_stock`: `order_resv_ccnl` (주식예약주문조회)
- `overseas_stock`: `order_resv_list`(예약주문조회), `algo_ordno`(주문번호조회)

> ⚠️ 같은 이름이라도 도구마다 의미가 다르다. `order_resv_ccnl` 은 **국내=조회**,
> **해외=예약접수취소(주문)** 이라 도구별로 분리해 판단한다.

### 한계 — 이건 "로컬 가드레일"이다

이 훅은 **당신 머신에서 Claude Code 로 띄울 때만** 작동한다. MCP 의 속성이 아니다.

- `settings.local.json` 이 gitignore 라 clone 해도 **꺼진 상태**다.
- 훅은 클라이언트(Claude Code) 기능 — Docker 이미지/npx 배포본 안에서 실행되지 않는다
  (`.claude/` 는 Docker 빌드 컨텍스트 밖이다).
- Claude Desktop·Cursor·SDK 등 **다른 MCP 클라이언트는 이 훅을 전혀 모른다** →
  주문 확인 없이 그대로 체결된다.

→ 배포본 사용자 전원에게 강제하려면 **서버 측 가드**가 있어야 한다(아래 3장).

---

## 3. 향후 TODO — 서버 측 env 플래그 가드

> **상태: 예정(미구현).** 코드 위치에 `TODO` 주석이 있다 → `tools/base.py` 의 `_run()`.

### 목표

주문 확인을 **MCP 자체의 속성**으로 만들어, 어떤 클라이언트로 연결하든 / 배포본을
쓰든 동일하게 적용되게 한다.

### 방식: 환경변수 플래그

| env | 의미 |
|---|---|
| `REQUIRE_ORDER_CONFIRMATION` | `true`(기본 권장)면 주문 api_type 실행 전 확인 토큰을 요구. 없으면 차단. |
| (선택) `ORDER_GUARD_MODE` | `block`(기본) / `dry_run`(주문 시뮬레이션만) / `off` |

### 구현 위치

`tools/base.py` → `BaseTool._run()` 의 **step 3(api_type 검증) 직후, step 4/5(실행) 직전.**
이미 `TODO(order-guard)` 주석을 달아 두었다.

### 동작 스케치

```python
# _run() 내부, api_type 이 config 에 존재함을 확인한 직후
if self._is_order_api(api_type):                      # 2장의 주문 api_type 집합 재사용
    if os.getenv("REQUIRE_ORDER_CONFIRMATION", "true").lower() == "true":
        if not params.get("confirm_token"):
            return {
                "ok": False,
                "error": "ORDER_CONFIRMATION_REQUIRED",
                "message": f"주문 동작({api_type})입니다. 확인 후 confirm_token 과 함께 다시 호출하세요.",
                "preview": {"api_type": api_type, "params": params},
            }
```

- **주문 api_type 집합**은 클라 훅(`kis-order-guard.py`)의 `EXPLICIT_WRITE` 와
  **동일 기준**으로 둔다. 향후 두 곳이 어긋나지 않도록, 가능하면 분류 로직을
  공용 모듈(예: `module/order_classifier.py`)로 빼서 훅과 서버가 함께 쓰게 한다.
- MCP **elicitation**(`ctx.elicit(...)`)을 쓰면 confirm_token 왕복 없이 서버가 직접
  "정말 주문할까요?"를 띄울 수 있다(클라이언트가 elicitation 지원 시). env 플래그 방식과
  병행 가능 — 우선은 토큰/차단 방식이 호환성이 넓다.

### 배포 문서화

구현 시 `Readme.md` 의 Docker 실행 예시에 `-e REQUIRE_ORDER_CONFIRMATION=true` 를
추가하고, 기본값/동작을 환경변수 표에 명시한다.

---

## 4. 두 계층의 관계

| | 클라이언트 훅 (현재) | 서버 env 가드 (예정) |
|---|---|---|
| 적용 범위 | 내 로컬 Claude Code 세션 | MCP 배포본 전체·모든 클라이언트 |
| 강제력 | 약함(끄기 쉬움, 배포 안 됨) | 강함(서버가 직접 거부) |
| 역할 | 평소 작업 편의 + 1차 가드레일 | 최종 안전장치 |

둘은 **보완 관계**다. 서버 가드가 들어와도 클라 훅은 "조회는 무프롬프트, 주문만 확인"
이라는 일상 UX 를 위해 유지할 가치가 있다.
