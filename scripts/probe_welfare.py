"""탐침 — 한국사회보장정보원_중앙부처복지서비스 API의 실제 응답을 그대로 받아 둔다. 표준 라이브러리만.

왜: 응답 필드 이름과 파라미터 의미를 기억으로 짐작해 파서를 짜지 않으려고. 이 탐침이 받은 XML이 파서 시험의 픽스처가 된다.
호출 3회 — ①목록(서비스명 「기초연금」 검색) ②목록 1페이지 ③①에서 찾은 첫 서비스의 상세. 개발 계정 하루 100건 중 3건.

실행 (PowerShell, 한 블록에 한 명령):
    $env:DATA_GO_KR_KEY = "발급받은 일반 인증키"
    & "C:\\Users\\cas\\AppData\\Local\\Programs\\Python\\Python312\\python.exe" "C:\\Users\\cas\\Documents\\GitHub\\public-ai-audit\\scripts\\probe_welfare.py"

🔴 키는 환경변수 DATA_GO_KR_KEY 로만 읽는다. 화면·로그·저장 파일 어디에도 키를 남기지 않는다(가림 처리).
   인코딩판(%2B …)을 넣어도 한 번 풀어서 쓴다 — 그대로 쓰면 두 번 인코딩돼 SERVICE_KEY_IS_NOT_REGISTERED 가 난다.
결과: data/welfare/_probe/ (git·Vercel 모두 제외). 설계: 볼트 30_projects/공공AI_감리/20_설계/02_감리_복지원문대조_설계
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus, unquote, urlencode

BASE = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "welfare" / "_probe"
KST = timezone(timedelta(hours=9), "KST")

CALLS = [
    ("list_search", "NationalWelfarelistV001",
     {"callTp": "L", "pageNo": "1", "numOfRows": "10", "srchKeyCode": "001", "searchWrd": "기초연금"}),
    ("list_page1", "NationalWelfarelistV001",
     {"callTp": "L", "pageNo": "1", "numOfRows": "10", "srchKeyCode": "003"}),
]


def normalize_key(key: str | None) -> str:
    """인코딩판이면 한 번 풀고, 앞뒤 공백을 지운다."""
    key = (key or "").strip()
    return unquote(key) if "%" in key else key


def build_url(op: str, params: dict, key: str) -> str:
    return f"{BASE}/{op}?" + urlencode({"serviceKey": key, **params})


def redact(text: str, key: str) -> str:
    """키의 모든 표기(원문·%인코딩·+인코딩)를 ***로 가린다."""
    if not key:
        return text
    for form in sorted({key, quote(key, safe=""), quote_plus(key)}, key=len, reverse=True):
        text = text.replace(form, "***")
    return text


def first_serv_id(xml: str) -> str | None:
    m = re.search(r"<servId>\s*([^<\s]+)\s*</servId>", xml or "")
    return m.group(1) if m else None


def _fetch(url: str, timeout: int = 20) -> tuple[object, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except urllib.error.URLError as e:
        return "NETWORK", repr(e.reason)


def main() -> int:
    key = normalize_key(os.environ.get("DATA_GO_KR_KEY"))
    if not key:
        print("환경변수 DATA_GO_KR_KEY 가 없습니다. PowerShell에서 먼저: $env:DATA_GO_KR_KEY = \"발급받은 키\"")
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    meta, bodies, failed = [], {}, False

    def run(name: str, op: str, params: dict) -> None:
        nonlocal failed
        status, body = _fetch(build_url(op, params, key))
        body = redact(body, key)
        path = OUT / f"{stamp}_{name}.xml"
        path.write_text(body, encoding="utf-8", newline="\n")
        bodies[name] = body
        failed = failed or status == "NETWORK"
        meta.append({"name": name, "op": op, "params": params, "status": status, "chars": len(body), "file": path.name})
        preview = re.sub(r"\s+", " ", body)[:200]
        print(f"[{name}] {op} {params} → {status}, {len(body)}자\n    {preview}")

    for name, op, params in CALLS:
        run(name, op, params)
    serv_id = first_serv_id(bodies.get("list_search", ""))
    if serv_id:
        run("detail", "NationalWelfaredetailedV001", {"callTp": "D", "servId": serv_id})
    else:
        print("[detail] 목록 응답에서 servId를 찾지 못해 상세 호출을 건너뛴다 — 위 목록 응답을 확인")

    (OUT / f"{stamp}_meta.json").write_text(json.dumps({"at": stamp, "calls": meta}, ensure_ascii=False, indent=2),
                                            encoding="utf-8", newline="\n")
    print(f"\n저장: {OUT}  (호출 {len(meta)}회 · 키는 어디에도 저장하지 않았다)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
