# 중요 : MCP에 대한 내용을 완전히 숙지하신 뒤 사용해 주십시오. 
#       이 프로그램을 실행하여 발생한 모든 책임은 사용자 본인에게 있습니다.

# 한국투자증권 OPEN API MCP 서버 - Docker 설치 가이드

한국투자증권의 다양한 금융 API를 Docker를 통해 Claude Desktop에서 쉽게 사용할 수 있도록 하는 설치 가이드입니다.

## 🚀 주요 기능

### 지원하는 API 카테고리

| 카테고리 | 개수 | 주요 기능 |
|---------|------|----------|
| 국내주식 | 74개 | 현재가, 호가, 차트, 잔고, 주문, 순위분석, 시세분석, 종목정보, 실시간시세 등 |
| 해외주식 | 34개 | 미국/아시아 주식 시세, 잔고, 주문, 체결내역, 거래량순위, 권리종합 등 |
| 국내선물옵션 | 20개 | 선물옵션 시세, 호가, 차트, 잔고, 주문, 야간거래, 실시간체결 등 |
| 해외선물옵션 | 19개 | 해외선물 시세, 주문내역, 증거금, 체결추이, 옵션호가 등 |
| 국내채권 | 14개 | 채권 시세, 호가, 발행정보, 잔고조회, 주문체결내역 등 |
| ETF/ETN | 2개 | NAV 비교추이, 현재가 등 |
| ELW | 1개 | ELW 거래량순위 |

**전체 API 총합계: 166개**

### 핵심 특징
- 🐳 **Docker 컨테이너화**: 완전 격리된 환경에서 안전한 실행
- ⚡ **동적 코드 실행**: GitHub에서 실시간으로 API 코드를 다운로드하여 실행
- 🔧 **설정 기반**: JSON 파일로 API 설정 및 파라미터 관리
- 🛡️ **안전한 실행**: 격리된 임시 환경에서 코드 실행
- 🔍 **검증 기능**: API 상세 정보 조회로 파라미터 확인
- 🌍 **환경 지원**: 실전/모의 환경 구분 지원
- 🔐 **자동 설정**: 서버 시작 시 KIS 인증 설정 자동 생성
- 🖥️ **크로스 플랫폼**: Windows, macOS, Linux 모두 지원

> ⚠️ **주문 안전장치**: 조회는 자동 허용하되 주문(매수/매도/정정/취소)만 사용자 승인을
> 받도록 하는 가드의 설계·구현과, 향후 서버 측 강제 가드(예정) 방법은
> [docs/order-permission-guard.md](docs/order-permission-guard.md) 를 참고하세요.

## 🚀 실행 방법은 두 가지입니다

| 방법 | 추천 대상 | 특징 |
|------|----------|------|
| **A. 로컬 서버 직접 실행** | Claude Code / Claude Desktop / Cursor 사용자 | Docker 불필요. `uv` 로 바로 실행, stdio 연결. **가장 간단.** |
| **B. Docker 컨테이너** | 격리 환경 / HTTP(SSE) 배포 | 컨테이너로 격리, HTTP 서버로 노출. |

> 처음이라면 **방법 A(로컬 서버 직접 실행)** 를 권장합니다. Docker 가 필요 없습니다.

---

## ⚡ 방법 A: 로컬 서버 직접 실행 (Docker 없이)

Claude Code·Claude Desktop·Cursor 같은 MCP 클라이언트가 `uv` 로 `server.py` 를
**stdio 모드**로 직접 띄우는 방식입니다.

### 0단계: 사전 준비
- **Python 3.11 이상**
- **`uv`** (Python 패키지/실행 관리자) — 없으면 설치:
  ```bash
  # macOS / Linux
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Windows PowerShell
  powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- 한국투자증권 OPEN API **App Key / App Secret**(모의·실전)과 **계좌번호**

### 1단계: 클론 & 의존성 설치
```bash
git clone https://github.com/koreainvestment/open-trading-api.git
cd "open-trading-api/MCP/Kis Trading MCP"
uv sync
```

### 2단계: 환경설정 파일 `.env.paper` 만들기  ⭐가장 중요
서버는 `ENV` 값(**`paper`=모의투자 / `live`=실전투자**)에 따라 **같은 폴더의
`.env.{ENV}`** 파일을 읽습니다. 이 파일이 없으면 서버는 기동 즉시 종료됩니다.

모의투자부터 시작하므로 `.env.paper` 를 만듭니다:
```bash
cp .env.example .env.paper
```
그런 다음 `.env.paper` 를 열어 발급받은 값을 채웁니다(평문):
```ini
MCP_TYPE=stdio
KIS_APP_KEY=발급받은_실전_APP_KEY
KIS_APP_SECRET=발급받은_실전_APP_SECRET
KIS_PAPER_APP_KEY=발급받은_모의_APP_KEY
KIS_PAPER_APP_SECRET=발급받은_모의_APP_SECRET
KIS_HTS_ID=내_HTS_ID
KIS_ACCT_STOCK=12345678        # 실전 주식 계좌 앞 8자리
KIS_ACCT_FUTURE=12345678       # 실전 선물옵션 계좌 앞 8자리 (주식과 같아도 됨)
KIS_PAPER_STOCK=50123456       # 모의 주식 계좌
KIS_PAPER_FUTURE=50123456      # 모의 선물옵션 계좌 (주식과 같아도 됨)
KIS_PROD_TYPE=01               # 계좌 뒤 2자리: 01 종합 / 03 국내선옵 / 08 해외선옵 ...
```
> `.env.paper` / `.env.live` 는 `.gitignore` 에 있어 git 에 올라가지 않습니다(비밀 보호).
> 더 안전하게 1Password 로 관리하려면 아래 **"🔐 방법 A-보안: 1Password(op://)로 비밀 관리"** 섹션 참고.

### 3단계: 단독 실행으로 동작 확인 (선택이지만 권장)
MCP 클라이언트에 붙이기 전에, 서버가 정상 기동하는지 확인합니다:
```bash
ENV=paper uv run python server.py
```
로그에 `🚀 MCP 서버를 stdio 모드로 시작합니다...` 가 보이면 정상입니다.
stdio 모드라 그 뒤 **입력 대기 상태로 멈춰 있는 게 정상**입니다 — `Ctrl+C` 로 종료하세요.
(오류로 바로 종료되면 대부분 `.env.paper` 누락/값 오류입니다.)

### 4단계: MCP 클라이언트에 등록

먼저 두 값을 확인해 두세요:
```bash
which uv   # uv 절대경로 (예: /Users/username/.local/bin/uv)  ※ Windows 는 where uv
pwd        # "MCP/Kis Trading MCP" 폴더의 절대경로
```

#### ① Claude Code (CLI)
레포 루트(`open-trading-api/`)에서 실행:
```bash
claude mcp add kis-trade-mcp --scope local --env ENV=paper \
  -- uv run --directory "/절대경로/open-trading-api/MCP/Kis Trading MCP" python server.py
```
- `/절대경로/...` 는 위 `pwd` 로 확인한 실제 경로로 바꾸세요.
- 등록 후 **Claude Code 를 재시작**해야 서버가 로드됩니다(MCP 는 시작 시 1회만 로드).
- 확인: `claude mcp list` → `kis-trade-mcp ... ✔ Connected`

#### ② Claude Desktop
설정 파일에 아래를 추가하고 앱을 재시작합니다.
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
```json
{
  "mcpServers": {
    "kis-trade-mcp": {
      "command": "/Users/username/.local/bin/uv",
      "args": [
        "run", "--directory",
        "/절대경로/open-trading-api/MCP/Kis Trading MCP",
        "python", "server.py"
      ],
      "env": { "ENV": "paper" }
    }
  }
}
```
- `command` 는 위 `which uv` 로 확인한 **uv 절대경로**.
- `args` 의 `--directory` 는 **`MCP/Kis Trading MCP` 폴더의 절대경로**.

#### ③ Cursor
`Settings > MCP Servers` 에서 위 Claude Desktop 과 **동일한 JSON**(stdio)을 사용합니다.

### 실전(live) 전환
실전투자로 바꾸려면 `.env.live` 를 만들어 값을 채우고, 등록 시 `ENV` 를 `live` 로 바꿉니다
(Claude Code 는 `--env ENV=live`, Desktop/Cursor 는 `"env": { "ENV": "live" }`).
**반드시 모의(paper)로 충분히 검증한 뒤** 전환하세요.

---

## 🔐 방법 A-보안: 1Password(op://)로 비밀 관리 (선택)

평문 키를 디스크에 두기 싫다면, `.env.{env}` 값에 **`op://` 참조**를 적을 수 있습니다.
서버 기동 시 1Password 에서 실제 값을 읽어 메모리로만 주입합니다(평문 파일에 비밀이 남지 않음).

```ini
# .env.paper (op:// 방식)
MCP_TYPE=stdio
OP_ACCOUNT=my.1password.com
KIS_APP_KEY=op://Private/kis-trading/KIS_APP_KEY
KIS_APP_SECRET=op://Private/kis-trading/KIS_APP_SECRET
# ... (나머지 키도 동일하게 op://vault/item/field 형식)
KIS_PROD_TYPE=01
```

인증 수단은 다음 우선순위로 **자동 선택**됩니다(`module/plugin/onepassword.py`):

| 우선순위 | 수단 | 사용 상황 |
|---|---|---|
| 1 | `op` CLI (`op read`) | 로컬 세션 / Service Account 토큰 / 앱 연동 모두 처리. SSH 친화. |
| 2 | SDK + `OP_SERVICE_ACCOUNT_TOKEN` | 무인(헤드리스) 자동화. |
| 3 | SDK + 데스크톱 앱(Touch ID) | 로컬 GUI 폴백. |

- **로컬 GUI(맥)**: 1Password 데스크톱 앱이 켜져 있으면 기동 시 Touch ID 승인만 하면 됩니다.
- **SSH/헤드리스**: GUI Touch ID 가 없으므로 `scripts/ssh-start.sh` 로 Claude Code 를 띄우세요.
  이 런처가 `op signin` 으로 세션을 만든 뒤 그 세션을 물려받아 서버를 기동합니다.
  ```bash
  ./scripts/ssh-start.sh            # 1Password 로그인 후 claude 기동
  OP_ACCOUNT=my ./scripts/ssh-start.sh
  ```
- 평문 값(op:// 아님)은 그대로 쓰이므로 1Password 미사용 환경과 완전히 하위호환됩니다.

---

## 📦 방법 B: Docker 설치 및 설정

### 📋 Docker 설치

#### 🚀 빠른 설치 (권장)
**공식 Docker Desktop을 사용하세요:**
- [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop/)
- [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/)  
- [Docker Engine for Linux](https://docs.docker.com/engine/install/)

#### 📋 OS별 간단 가이드

##### 🍎 **macOS**
```bash
# Homebrew 사용 (권장)
brew install --cask docker

# 또는 공식 인스톨러 다운로드
# https://www.docker.com/products/docker-desktop/
```

##### 🐧 **Linux (Ubuntu/Debian)**  
```bash
# 공식 스크립트 사용 (권장)
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
```

##### 🪟 **Windows**
**⚠️ Windows는 추가 설정이 필요합니다:**

1. **시스템 요구사항 확인**
   - Windows 10/11 Pro, Enterprise, Education
   - WSL2 또는 Hyper-V 지원

2. **Docker Desktop 설치**
   - [공식 사이트](https://www.docker.com/products/docker-desktop/)에서 다운로드
   - 설치 중 "Use WSL 2" 옵션 선택 권장

3. **설치 후 확인**
   ```cmd
   docker --version
   docker run hello-world
   ```

**Windows 상세 설치 가이드**: [Docker 공식 문서](https://docs.docker.com/desktop/install/windows-install/) 참조

### 요구사항
- Docker 20.10+
- 한국투자증권 OPEN API 계정

### 📋 설치 및 설정 단계

#### **1단계: 프로젝트 클론**
```bash
# 프로젝트 클론
git clone https://github.com/koreainvestment/open-trading-api.git
cd "open-trading-api/MCP/Kis Trading MCP"
```

#### **2단계: 한국투자증권 API 정보 준비**
한국투자증권 개발자 센터에서 발급받은 정보를 준비하세요:

**필수 정보:**
- App Key (실전용)
- App Secret (실전용)
- 계좌 정보들

**선택 정보:**
- App Key (모의용)
- App Secret (모의용)

#### **3단계: Docker 이미지 빌드**
```bash
# Docker 이미지 빌드
docker build -t kis-trade-mcp .

# 또는 태그와 함께 빌드
docker build -t kis-trade-mcp:latest .
```

#### **4단계: Docker 컨테이너 실행**

**기본 실행:**
```bash
docker run -d \
  --name kis-trade-mcp \
  -p 3000:3000 \
  -e KIS_APP_KEY="your_app_key" \
  -e KIS_APP_SECRET="your_app_secret" \
  -e KIS_PAPER_APP_KEY="your_paper_app_key" \
  -e KIS_PAPER_APP_SECRET="your_paper_app_secret" \
  -e KIS_HTS_ID="your_hts_id" \
  -e KIS_ACCT_STOCK="12345678" \
  -e KIS_ACCT_FUTURE="87654321" \
  -e KIS_PAPER_STOCK="11111111" \
  -e KIS_PAPER_FUTURE="22222222" \
  -e KIS_PROD_TYPE="01" \
  kis-trade-mcp
```

#### **5단계: 컨테이너 상태 확인**
```bash
# 컨테이너 상태 확인
docker ps

# 컨테이너 로그 확인
docker logs kis-trade-mcp

# 실시간 로그 확인
docker logs -f kis-trade-mcp

# HTTP 서버 접근 확인
curl http://localhost:3000/sse
```

#### **6단계: HTTP 서버 접근 확인**
컨테이너가 정상적으로 실행되면 HTTP 서버에 접근할 수 있습니다:

```bash
# 서버 상태 확인
curl http://localhost:3000/sse

# 또는 브라우저에서 접근
# http://localhost:3000/sse
```

### 🔗 Claude Desktop 연동 및 설정

#### 📝 Claude Desktop 설정
Claude Desktop 설정 파일에 MCP 서버를 등록하세요.

**설정 파일 위치:**
- **Linux/Mac**: `~/.claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### 🐧 Linux/Mac 설정
```json
{
  "mcpServers": {
    "kis-trade-mcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:3000/sse"]
    }
  }
}
```

#### 🪟 Windows 설정
```json
{
  "mcpServers": {
    "kis-trade-mcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:3000/sse"]
    }
  }
}
```

## 💬 사용법 및 질문 예시

### 기본 사용 패턴

1. **종목 검색**: 먼저 종목 코드를 찾습니다
2. **API 확인**: 사용할 API의 파라미터를 확인합니다  
3. **API 호출**: 필요한 파라미터와 함께 API를 호출합니다

### 질문 예시

**주식 시세 조회:**
- "삼성전자(005930) 현재가 시세 조회해줘"
- "애플(AAPL) 해외주식 현재 체결가 알려줘"
- "삼성전자 종목코드 찾아줘"

**잔고 및 계좌:**
- "국내주식 잔고 조회해줘"
- "해외주식 잔고 확인해줘"

**채권 및 기타:**
- "국고채 3년물 호가 정보 조회하는 방법"
- "KODEX 200 ETF(069500) NAV 비교추이 확인해줘"

**모의투자:**
- "모의투자로 삼성전자 현재가 조회해줘"
- "데모 환경에서 애플 주식 시세 알려줘"

## 🔧 컨테이너 관리

### 컨테이너 제어
```bash
# 컨테이너 시작
docker start kis-trade-mcp

# 컨테이너 중지
docker stop kis-trade-mcp

# 컨테이너 재시작
docker restart kis-trade-mcp

# 컨테이너 제거
docker stop kis-trade-mcp
docker rm kis-trade-mcp
```

### 컨테이너 내부 접근
```bash
# 컨테이너 내부 bash 실행
docker exec -it kis-trade-mcp /bin/bash

# 환경변수 확인
docker exec kis-trade-mcp env | grep KIS

# 로그 실시간 확인
docker logs -f kis-trade-mcp
```

## 💡 사용 팁

1. **환경변수 관리**: 민감한 정보는 환경변수로 안전하게 관리
2. **로그 모니터링**: `docker logs -f`로 실시간 로그 확인
3. **리소스 모니터링**: `docker stats`로 컨테이너 리소스 사용량 확인
4. **백업 전략**: 중요한 설정 파일은 정기적으로 백업
5. **보안 관리**: 컨테이너 내부에서만 민감한 정보 처리

## 📝 로깅 및 모니터링

### 로그 확인
```bash
# 전체 로그
docker logs kis-trade-mcp

# 최근 100줄
docker logs --tail 100 kis-trade-mcp

# 실시간 로그
docker logs -f kis-trade-mcp

# 특정 시간대 로그
docker logs --since "2024-01-01T00:00:00" kis-trade-mcp
```

### 성능 모니터링
```bash
# 컨테이너 리소스 사용량
docker stats kis-trade-mcp

# 컨테이너 상세 정보
docker inspect kis-trade-mcp

# 프로세스 확인
docker exec kis-trade-mcp ps aux
```

## 🛠️ 문제 해결

### 일반적인 문제들

**1. 컨테이너가 시작되지 않는 경우**
```bash
# 로그 확인
docker logs kis-trade-mcp

# 환경변수 확인
docker exec kis-trade-mcp env | grep KIS
```

**2. 환경변수 누락**
```bash
# 컨테이너 재시작
docker restart kis-trade-mcp

# 환경변수 다시 설정하여 실행
docker run -d --name kis-trade-mcp -e KIS_APP_KEY="..." ...
```

**3. 메모리 부족**
```bash
# 메모리 사용량 확인
docker stats kis-trade-mcp

# 컨테이너 리소스 제한 설정
docker run -d --name kis-trade-mcp --memory="2g" --cpus="2" ...
```

**4. 네트워크 연결 문제**
```bash
# 포트 확인
docker port kis-trade-mcp

# 네트워크 연결 테스트
curl http://localhost:3000/sse
```

### 디버깅 명령어
```bash
# 컨테이너 내부 bash 접근
docker exec -it kis-trade-mcp /bin/bash

# Python 환경 확인
docker exec kis-trade-mcp uv run python -c "import sys; print(sys.path)"

# 의존성 확인
docker exec kis-trade-mcp uv pip list

# 네트워크 연결 확인
docker exec kis-trade-mcp ping github.com
```

## 🔒 보안 고려사항

- **컨테이너 격리**: 호스트 시스템과 완전히 분리된 환경에서 실행
- **환경변수 보안**: 민감한 정보는 환경변수로 전달, 코드에 하드코딩 금지
- **임시 파일 정리**: 각 API 호출 후 임시 파일 자동 삭제
- **네트워크 격리**: 필요한 경우 Docker 네트워크를 통한 추가 격리

## ⚠️ 제한사항 및 성능

### API 호출 제한
- 한국투자증권 API의 호출 제한을 준수해야 합니다
- 분당 호출 횟수 제한이 있을 수 있습니다
- 실전 환경에서는 더욱 신중한 사용이 필요합니다

### Docker 성능 고려사항
- **컨테이너 오버헤드**: Docker 컨테이너 실행으로 인한 약간의 성능 오버헤드
- **메모리 사용량**: SQLAlchemy와 pandas가 메모리를 많이 사용할 수 있음
- **네트워크 지연**: GitHub 다운로드 시 네트워크 지연 발생

### 다단계 타임아웃 설정
- 파일 다운로드: 30초 (GitHub 응답 대기)
- 코드 실행: 15초 (API 호출 및 결과 처리)
- 컨테이너 시작: 60초 (의존성 설치 및 초기화)

## 🔗 관련 링크

- [한국투자증권 개발자 센터](https://apiportal.koreainvestment.com/)
- [한국투자증권 OPEN API GitHub](https://github.com/koreainvestment/open-trading-api)
- [MCP (Model Context Protocol) 공식 문서](https://modelcontextprotocol.io/)
- [Docker 공식 문서](https://docs.docker.com/)

---

**주의**: 이 프로젝트는 한국투자증권 OPEN API를 사용합니다. 사용 전 반드시 [한국투자증권 개발자 센터](https://apiportal.koreainvestment.com/)에서 API 이용약관을 확인하시기 바랍니다.

## ⚠️ 투자 책임 고지

**본 MCP 서버는 한국투자증권 OPEN API를 활용한 도구일 뿐이며, 투자 조언이나 권유를 제공하지 않습니다.**

- 📈 **투자 결정 책임**: 모든 투자 결정과 그에 따른 손익은 전적으로 투자자 본인의 책임입니다
- 💰 **손실 위험**: 주식, 선물, 옵션 등 모든 금융상품 투자에는 원금 손실 위험이 있습니다
- 🔍 **정보 검증**: API를 통해 제공되는 정보의 정확성은 한국투자증권에 의존하며, 투자 전 반드시 정보를 검증하시기 바랍니다
- 🧠 **신중한 판단**: 충분한 조사와 신중한 판단 없이 투자하지 마시기 바랍니다
- 🎯 **모의투자 권장**: 실전 투자 전 반드시 모의투자를 통해 충분히 연습하시기 바랍니다

**투자는 본인의 판단과 책임 하에 이루어져야 하며, 본 도구 사용으로 인한 어떠한 손실에 대해서도 개발자는 책임지지 않습니다.**
