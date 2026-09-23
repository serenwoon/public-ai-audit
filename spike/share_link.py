"""결과 링크 — 서버에 아무것도 저장하지 않고, 답변을 링크의 # 뒤에 싣는다. 순수 함수, 네트워크 없음.

형식(브라우저 public/share.js 와 같다):  {base}/#v=1&d=YYYY-MM-DD&a=<base64url(zlib(답변))>[&s=<base64url(zlib(상황))>]
- # 뒤(fragment)는 서버로 가지 않는다 — 답변이 우리 로그에도 Vercel에도 남지 않는다
- d 는 규칙이 쓴 날짜다. 며칠 뒤에 열어도 같은 날 기준으로 다시 계산해 카카오에서 본 결과와 같게 한다
- 카카오 버튼 URL 길이 한도는 문서로 확인하지 못했다 → 안전 상한 MAX_LINK. 넘으면 None (9/24 실측 항목)

모듈 이름이 share 가 아닌 이유: 파이썬 설치 폴더의 share/ 디렉터리가 이름공간 패키지로 잡힌다 (2026-09-23 발견).
"""
from __future__ import annotations

import base64
import re
import zlib
from datetime import date
from urllib.parse import urlencode

MAX_LINK = 1800
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _pack(s: str) -> str:
    return base64.urlsafe_b64encode(zlib.compress(s.encode("utf-8"), 9)).decode("ascii").rstrip("=")


def fragment(text: str, situation: str = "", day: date | None = None) -> str:
    q = [("v", "1")]
    if day:
        q.append(("d", day.isoformat()))
    q.append(("a", _pack(text)))
    if situation:
        q.append(("s", _pack(situation)))
    return urlencode(q)


def result_link(base_url: str, text: str, situation: str = "", day: date | None = None,
                limit: int = MAX_LINK) -> str | None:
    """이 답변의 감리 결과를 여는 링크. 상한을 넘으면 None — 부르는 쪽이 첫 화면으로 대신한다."""
    link = base_url.rstrip("/") + "/#" + fragment(text, situation, day)
    return link if len(link) <= limit else None


def parse_day(value) -> date | None:
    """'YYYY-MM-DD' → date. 형식이 다르거나 없는 날짜면 None."""
    if not isinstance(value, str) or not _DAY.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
