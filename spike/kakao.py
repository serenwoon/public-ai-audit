"""카카오 i 오픈빌더 스킬 요청/응답 — 순수 함수만. 네트워크 없음.

규격 출처: 카카오 비즈니스 「AI 챗봇 콜백 개발 가이드」
https://kakaobusiness.gitbook.io/main/tool/chatbot/skill_guide/ai_chatbot_callback_guide
- 콜백 URL: userRequest.callbackUrl (1회성)
- 즉시 응답(콜백 사용): {"version":"2.0","useCallback":true,"context":{},"data":{"text":...}}  # template 없음
- 최종 응답: 콜백 URL로 POST, 본문은 일반 스킬 응답과 동일
"""
from __future__ import annotations

import json
import re

VERSION = "2.0"
MAX_DELAY = 600  # 초. 실측용 상한

_DELAY_RE = re.compile(r"(?:지연|delay)\s*(\d{1,3})", re.IGNORECASE)


def parse_request(payload: dict) -> dict:
    """스킬 요청에서 필요한 값만 안전하게 뽑는다. 없으면 None/빈 문자열."""
    user_req = payload.get("userRequest") or {}
    user = user_req.get("user") or {}
    bot = payload.get("bot") or {}
    intent = payload.get("intent") or {}
    return {
        "utterance": (user_req.get("utterance") or "").strip(),
        "user_id": user.get("id"),
        "callback_url": user_req.get("callbackUrl"),
        "bot_id": bot.get("id"),
        "intent_name": intent.get("name"),
        "lang": user_req.get("lang"),
    }


def parse_delay(utterance: str) -> int | None:
    """'지연 30' / 'delay 30' → 30. 없으면 None. 상한 MAX_DELAY."""
    m = _DELAY_RE.search(utterance or "")
    if not m:
        return None
    return min(int(m.group(1)), MAX_DELAY)


def simple_text(text: str) -> dict:
    return {"version": VERSION, "template": {"outputs": [{"simpleText": {"text": text}}]}}


def callback_wait(text: str) -> dict:
    """콜백을 쓰겠다는 즉시 응답. template을 넣지 않는다."""
    return {"version": VERSION, "useCallback": True, "context": {}, "data": {"text": text}}


def echo_text(utterance: str, limit: int = 300) -> str:
    """받은 발화를 그대로 되돌려 보여준다 — 「전달」된 메시지가 어떤 형태로 오는지 눈으로 확인하려고."""
    body = utterance if len(utterance) <= limit else utterance[:limit] + "…"
    return f"받았어요 ({len(utterance)}자)\n\n{body}"


# ---- 감리 결과 → 카카오 응답 -------------------------------------------------
# 오픈빌더 제약: 스킬 응답의 outputs 는 최대 3개. 그래서 세 덩어리로 묶는다.
#   1) 요약 + 주장별 등급 (simpleText)   2) 되물을 질문 (simpleText, 번호)   3) 오늘 할 행동 + 「웹에서 자세히」 버튼 (basicCard)
MAX_OUTPUTS = 3
_TEXT_LIMIT = 1000  # simpleText 한 덩어리 안전 길이


def _clip(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def audit_outputs(result: dict, base_url: str | None = None) -> dict:
    """engine.audit() 결과를 스킬 응답(outputs 3개)으로 만든다."""
    s = result.get("summary") or {}
    claims = result.get("claims") or []
    head = f"주장 {len(claims)}개 — ✅{s.get('확인됨', 0)} ❌{s.get('틀림', 0)} ⚠️{s.get('말하지 않은 조건', 0)} ❓{s.get('확인 불가', 0)}"
    lines = [head, ""]
    for c in claims[:8]:
        lines.append(f"{c.get('mark', '❓')} [{c.get('type', '기타')}] {_clip(c.get('text', ''), 90)}")
    if len(claims) > 8:
        lines.append(f"… 외 {len(claims) - 8}개는 웹에서")
    first = _clip("\n".join(lines), _TEXT_LIMIT)

    qs = result.get("questions") or []
    if qs:
        second = _clip("그 AI에게 되물어 보세요 (길게 눌러 복사)\n\n" + "\n\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1)), _TEXT_LIMIT)
    else:
        second = "되물을 것이 없어요."

    card = {"title": "오늘 할 행동 하나", "description": _clip(result.get("action") or "", 200)}
    if base_url:
        card["buttons"] = [{"action": "webLink", "label": "웹에서 자세히", "webLinkUrl": base_url.rstrip("/") + "/"}]

    return {
        "version": VERSION,
        "template": {"outputs": [
            {"simpleText": {"text": first}},
            {"simpleText": {"text": second}},
            {"basicCard": card},
        ]},
    }


# ---- 요청 본문 해석 ----------------------------------------------------------
def decode_json(raw: bytes) -> tuple[dict | None, str | None]:
    """요청 본문 → (dict, None) 또는 (None, 오류 설명). 예외를 밖으로 내지 않는다.

    UTF-8이 아닌 바이트(예: 윈도우 콘솔의 cp949)나 깨진 JSON에 서버가 500으로 죽지 않게 한다.
    """
    if not raw:
        return {}, None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, "본문이 UTF-8이 아닙니다"
    try:
        obj = json.loads(text or "{}")
    except json.JSONDecodeError:
        return None, "JSON이 아닙니다"
    if not isinstance(obj, dict):
        return None, "JSON 객체가 아닙니다"
    return obj, None
