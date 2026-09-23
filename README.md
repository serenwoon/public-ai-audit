# public-ai-audit — 「믿어도 돼?」(가칭) 스파이크 (2026-09-22)

공공 AI(AI정부24·모두의 AI·온통청년 퓨봇)나 범용 AI가 준 답을 주장 단위로 쪼개 원문과 대조하고, 사람에게는 **되물을 질문 셋 + 오늘 할 행동 하나**를 돌려주는 감리 에이전트. 설계·근거는 볼트 `30_projects/공공AI_감리/`.

**지금은 스파이크다.** 엔진은 규칙 엔진 `rules-0.2`(`spike/engine.py`) — 주장 분해·유형 분류·규칙 판정·되물을 질문. 규칙은 아직 **시간 규칙 하나**(`spike/time_rule.py`)다: 지난 마감·기준 없는 상대 날짜·지난 연도 기준·「현재 모집 중」을 오늘(한국 시간)과 대조해 ⚠️를 붙인다. 원문이 없으니 ❌·✅는 만들지 않고, 나머지 주장은 ❓로 남는다. 다음 규칙은 복지서비스 원문 대조다. 이 저장소의 목적은 셋: ①카카오 봇 세 값 실측 ②웹 한 장과 API 계약 ③Vercel 배포 경로.

### 규칙 틀

규칙은 `rule(문장, 오늘) → {"grade","reason","expr","question"} 또는 None` 인 순수 함수다. `engine.RULES`에 더하면 된다. 한 주장에 판정이 여럿이면 **❌ > ⚠️ > ✅ > ❓** 순으로 센 것을 쓰고, 동점이면 앞선 규칙이 이긴다. 규칙이 만든 질문이 유형별 기본 질문보다 먼저 가고, 이미 다룬 유형의 기본 질문은 빠진다(최대 셋). 시험은 `audit(text, today=date(...))`로 날짜를 고정해 돈다. 결과에는 규칙이 쓴 날짜 `basis_date`가 남는다.

### 결과 링크 — 서버에 저장하지 않는다

카카오 카드의 「웹에서 자세히」와 웹의 「🔗 이 결과 링크 복사」는 **이 답변의 감리 결과**를 여는 링크다.

```
https://public-ai-audit.vercel.app/#v=1&d=2026-09-23&a=<base64url(zlib(답변))>[&s=<base64url(zlib(상황))>]
```

- 답변은 `#` 뒤에 실린다. `#` 뒤는 서버로 가지 않으므로 우리 로그에도 Vercel에도 남지 않는다. DB가 없다
- 웹은 링크를 열면 답변을 채우고 **`d`의 날짜 기준으로** 다시 감리한다(`/audit`의 `today`). 며칠 뒤 열어도 카카오에서 본 결과와 같다
- 파이썬 `spike/share_link.py`가 만들고 브라우저 `public/share.js`가 푼다. 두 쪽이 같은 형식을 쓰는지는 **node로 `share.js`를 그대로 돌리는 시험**(`tests/test_share.py`)이 양방향으로 확인한다. node가 없으면 그 시험만 건너뛴다
- 카카오 버튼 URL 한도는 문서로 확인하지 못해 **1,800자 상한**을 둔다. 넘으면 첫 화면 링크로 돌아가고 카드에 "답변이 길어 링크에 담지 못했어요"가 붙는다. 웹 복사 링크는 카톡 대화에 붙여 넣으므로 8,000자까지
- 링크는 결과가 나올 때 **미리 만든다.** 버튼을 누른 뒤 압축을 기다렸다 복사하면 아이폰 사파리(카카오톡 인앱 포함)가 클립보드 쓰기를 거부한다. 복사가 막히면 링크를 입력칸에 띄워 길게 눌러 복사하게 한다
- 모듈 이름이 `share`가 아닌 이유: 파이썬 설치 폴더의 `share/`가 이름공간 패키지로 잡힌다

## 배포 상태 (2026-09-23)

| | |
|---|---|
| 프로덕션 | **https://public-ai-audit.vercel.app** (별칭 public-ai-audit-serenwoon.vercel.app) — 계정 `serenwoon`, 프로젝트 `public-ai-audit` |
| 오픈빌더 스킬 URL | **https://public-ai-audit.vercel.app/skill** |
| 리전 | `icn1`(서울) — `vercel.json` `regions`. 첫 배포는 기본값 `iad1`(미국 동부)이었다 |
| 응답 (한국에서 잰 값) | `/audit` 0.06~0.31초 · `/skill` 0.08~0.30초 · `/health` 첫 호출 0.33초, 웜 중앙값 0.25초. `iad1` 때는 `/audit` 0.39 · `/skill` 0.47초 |
| 보호 | 프로덕션 도메인은 열려 있다(카카오가 닿아야 한다). 배포별 고유 주소(`…-serenwoon.vercel.app`)는 Vercel 보호가 걸릴 수 있으니 스킬 URL에 쓰지 않는다 |

배포하면서 고친 것 둘 — ①윈도우 git-bash의 curl이 한글을 cp949로 보내 `/audit`·`/skill`이 500이었다 → `kakao.decode_json()`으로 UTF-8·JSON 오류를 잡아 웹은 400, 카카오는 200 말풍선. **윈도우에서 한글로 시험할 때는 PowerShell `Invoke-RestMethod`(charset=utf-8)나 파이썬을 쓴다** ②확인 시각이 UTC(+00:00)로 찍혔다 → 엔진이 한국 시간(`+09:00`)으로 고정.

재배포:

```powershell
npx vercel deploy --prod --yes --cwd "C:\Users\cas\Documents\GitHub\public-ai-audit"
```

## 구조

```
api/skill.py      Vercel 함수 — 카카오 스킬 (동기 경로만, 5초 안)
api/audit.py      Vercel 함수 — POST {text, situation} → 감리 JSON
api/health.py
public/index.html 웹 한 장 (붙여넣기 → 카드 → 되물을 질문 복사 → 결과 링크 복사; 링크로 열면 자동 감리)
spike/engine.py   규칙 엔진 (순수 함수) — 분해·분류·RULES 판정·질문. audit() 계약은 유지
spike/time_rule.py 시간 규칙 (순수 함수) — 오늘 날짜를 주입받아 시점 표현 판정
spike/share_link.py 결과 링크 만들기 (순수 함수) — 답변을 # 뒤에 싣는다
public/share.js   결과 링크 풀기·만들기 (브라우저, node 시험 겸용)
spike/kakao.py    카카오 요청 파싱·응답 생성 (순수 함수)
spike/server.py   로컬 서버 — 위 전부 + 콜백 실측(「지연 N」)
tests/            소켓을 막고 도는 시험
vercel.json       rewrites: /skill /audit /health → api/*
```

## 로컬 — 윈도우 (한 블록에 한 명령)

시험:

```powershell
& "C:\Users\cas\AppData\Local\Programs\Python\Python312\python.exe" -m unittest discover -s "C:\Users\cas\Documents\GitHub\public-ai-audit\tests" -v
```

서버:

```powershell
& "C:\Users\cas\AppData\Local\Programs\Python\Python312\python.exe" "C:\Users\cas\Documents\GitHub\public-ai-audit\spike\server.py"
```

브라우저에서 `http://localhost:8000` — 웹 한 장. API 확인:

```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/audit" -ContentType "application/json; charset=utf-8" -Body '{"text":"만 19~34세 미취업 청년이면 신청하실 수 있습니다. 월 50만원을 6개월 지원합니다. 이번 달 말까지 온라인으로 신청하세요.","situation":"서울 27세"}'
```

## Vercel 배포

계정·로그인은 사용자가 한다. CLI는 npx로 (node 24 있음, vercel 미설치).

```powershell
npx vercel login
```

```powershell
npx vercel --cwd "C:\Users\cas\Documents\GitHub\public-ai-audit"
```

미리보기 주소가 나오면 확인:

```powershell
Invoke-RestMethod -Uri "https://<배포주소>/health"
```

정식 배포:

```powershell
npx vercel --cwd "C:\Users\cas\Documents\GitHub\public-ai-audit" --prod
```

- 환경변수 없음. 의존성 없음(`requirements.txt`는 주석뿐). Python 런타임은 `api/*.py`의 `class handler(BaseHTTPRequestHandler)` 규약 — one-step과 같다
- `maxDuration` 60초로 잡았다. one-step은 300이었으니 플랜이 허용하면 올려도 된다
- 오픈빌더 스킬 URL = `https://<배포주소>/skill`

### 🔴 호스팅 갈림길 — 콜백은 Vercel에서 하지 않는다

Vercel 서버리스는 **응답을 보낸 뒤의 작업을 보장하지 않는다.** 카카오 콜백(즉시 응답 → N초 뒤 콜백 URL로 POST)은 그 뒤 작업이다. Fluid Compute가 Python에서도 「백그라운드 처리」를 말하지만 Python용 `waitUntil`은 문서로 확인하지 못했다. 그래서 —

- `api/skill.py`는 **5초 안에 끝나는 동기 경로**만 둔다. 지금 엔진(규칙, 네트워크 없음)은 즉시 끝나므로 문제없다
- 콜백 실측(「지연 N」)은 **로컬 `spike/server.py` + cloudflared**로 한다
- 진짜 엔진(LLM + 원문 대조)이 5초를 넘기면 셋 중 하나를 고른다: ⓐ 스킬 엔드포인트만 Node 함수(`waitUntil`)로 두고 Python 감리를 부른다 ⓑ 백그라운드 워커가 되는 호스트(Render 등) ⓒ 즉시 응답에 「결과 보기」 링크만 주고 웹이 동기 처리 — 9/24 실측 뒤 결정

### 카카오 응답 제약 (코드에 반영됨)

- 스킬 응답 `outputs`는 **최대 3개** → ①요약+주장별 등급 ②되물을 질문(번호) ③오늘 할 행동 + 「웹에서 자세히」 버튼
- 콜백: 요청의 `userRequest.callbackUrl`(1회성), 즉시 응답 `{"version":"2.0","useCallback":true,"context":{},"data":{"text":…}}`(template 없음), 최종은 콜백 URL로 POST. 스킬 SLA 5초, 유효시간은 문서 5분/오류문구 1분 → 실측
- 🔴 **봇테스트에서는 콜백이 안 된다.** 배포 후 실제 채널에서

## 카카오 봇 실측 (9/24) — 로컬 서버로

| # | 실측할 값 | 어디서 보나 |
|---|---|---|
| ① | 다른 채팅의 메시지를 채널로 「전달」하면 **어떤 형태**로 도착하는가 | `logs/requests.jsonl` 의 `payload.userRequest.utterance` |
| ② | 요청에 **콜백 URL**이 실리는가 | 「지연 10」 → "감리 중이에요"면 O, "콜백 URL이 요청에 없어요"면 X |
| ③ | 콜백을 **몇 초 뒤까지** 받아주는가 | 「지연 10 / 50 / 70 / 120 / 240」 → `logs/callbacks.jsonl` 의 `status` |

노출:

```powershell
winget install --id Cloudflare.cloudflared
```

```powershell
cloudflared tunnel --url http://localhost:8000
```

`https://….trycloudflare.com/skill` 을 오픈빌더 스킬 URL에. 터널을 다시 켜면 주소가 바뀐다.

오픈빌더: 채널 → 챗봇 → 스킬 생성(URL) → **폴백 블록**에 연결, 「스킬 데이터 사용」 → 블록 더보기(…) > **Callback API 설정** → **배포** → 채널 채팅에서 아무 문장(①), 「지연 10」(②), 「지연 50/70/120/240」(③), 다른 채팅 메시지 **전달**(①).

## 실측 기록 → 볼트 `40_검증`

| 값 | 결과 | 날짜 |
|---|---|---|
| ① 전달 메시지 도착 형태 | | |
| ② 콜백 URL 실림 | O / X | |
| ③ 콜백 허용 초 | 10 __ · 50 __ · 70 __ · 120 __ · 240 __ | |
| 콜백 응답 본문 (status·message) | | |
| Vercel `/skill` 응답 시간 (콜드스타트 포함) | icn1 0.08~0.30초 (스텁) | 2026-09-23 |
| ④ 카카오 버튼 `webLinkUrl` 길이 한도 (결과 링크) | 긴 답변을 보내 버튼이 열리는지 — 상한 1,800자가 맞는가 | |
| ⑤ 아이폰·안드로이드 카톡 인앱에서 「🔗 이 결과 링크 복사」 | 클립보드 복사 O/X (미리보기 창은 클립보드를 막아 확인 못 함) | |
