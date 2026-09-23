"""감리 엔진 — 스텁(0.1). 순수 함수, 네트워크 없음.

지금은 「주장 분해 + 유형 분류 + 되물을 질문 틀」만 한다. 원문 대조가 없으므로 등급은 전부 「확인 불가」다.
진짜 엔진(원문 캐시·LLM·자기감리)이 들어오면 audit()의 계약(반환 JSON 모양)은 유지하고 속만 바꾼다.
계약은 볼트 30_projects/공공AI_감리/10_기획/01_감리_판정규칙_초안 을 따른다.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

ENGINE = "stub-0.1"
KST = timezone(timedelta(hours=9), "KST")  # 확인일은 한국 시간 — 서버(Vercel)는 UTC다
GRADES = ("확인됨", "틀림", "말하지 않은 조건", "확인 불가")
GRADE_MARK = {"확인됨": "✅", "틀림": "❌", "말하지 않은 조건": "⚠️", "확인 불가": "❓"}

# 우선순위 순서 — 앞에 있는 유형이 먼저 잡는다
_TYPE_RULES = [
    ("마감", re.compile(r"(마감|접수\s*기간|까지|기한|모집\s*기간|\d{1,2}\s*월\s*\d{1,2}\s*일|연중\s*상시|상시\s*접수)")),
    ("금액", re.compile(r"(\d[\d,]*\s*(만\s*원|원)|지원금|급여액)")),  # 「수당」은 정책 이름에 흔해 금액 신호로 안 쓴다
    ("자격", re.compile(r"(자격|대상|해당|만\s*\d{1,2}\s*세|\d{1,2}\s*세\s*(이상|이하|미만)|거주|소득|재산|미취업|졸업|무주택|기준\s*중위)")),
    ("절차", re.compile(r"(신청\s*(방법|하시|할 수|가능)|제출|온라인|방문|서류|접수처|홈페이지|앱에서|누리집)")),
    ("기관", re.compile(r"(법\s*제?\s*\d+\s*조|시행령|시행규칙|조례|주민센터|행정복지센터|센터|공단|공사|정부24|복지로|온통청년|보건소|구청|시청|군청)")),
]

_QUESTION_TEMPLATES = {
    "마감": "이번 회차 접수기간이 정확히 언제까지인지, 공고 번호나 원문 링크와 함께 알려주세요.",
    "자격": "제 상황({situation})에서 빠진 조건은 없는지 — 소득·재산·거주 기간·중복 수혜 제한이 있는지 알려주세요.",
    "금액": "그 금액이 어느 공고 기준인지, 지급 기간과 횟수까지 원문 그대로 알려주세요.",
    "절차": "신청할 때 내야 하는 서류와 신청처를 원문 기준으로 다시 확인해 주세요.",
    "기관": "인용한 법령이나 기관 안내가 지금도 현행인지, 개정일이 언제인지 알려주세요.",
    "기타": "이 내용의 근거가 되는 공고나 원문 링크를 알려주세요.",
}

_SPLIT_RE = re.compile(r"(?<=[.!?。])\s+|\n+")


_COURTESY_RE = re.compile(r"^(네|예|넵|감사합니다|고맙습니다|알겠습니다|안녕하세요|도움이\s*되셨길\s*바랍니다)[.!]?$")


def split_claims(text: str) -> list[str]:
    """문장 단위로 쪼갠다. 짧은 조각(8자 미만)과 인사말은 버린다 — 주장이 아니다."""
    parts = [p.strip(" \t-•·▪●") for p in _SPLIT_RE.split(text or "")]
    return [p for p in parts if len(p) >= 8 and not _COURTESY_RE.match(p)]


def classify(sentence: str) -> str:
    for name, rx in _TYPE_RULES:
        if rx.search(sentence):
            return name
    return "기타"


def audit(text: str, situation: str = "") -> dict:
    """스텁 감리. 등급은 전부 「확인 불가」, 이유는 원문 미확보."""
    sentences = split_claims(text)
    claims = []
    for i, s in enumerate(sentences, 1):
        claims.append({
            "id": i,
            "type": classify(s),
            "text": s,
            "grade": "확인 불가",
            "mark": GRADE_MARK["확인 불가"],
            "reason": "원문 미확보 — 엔진 전(스텁). 대조할 공고·법령을 아직 받지 않았다",
            "source": None,
        })

    # 되물을 질문 — 돈·기한을 잃을 수 있는 유형부터, 유형당 하나, 최대 셋
    questions: list[str] = []
    for t in ("마감", "자격", "금액", "절차", "기관", "기타"):
        if any(c["type"] == t for c in claims) and len(questions) < 3:
            questions.append(_QUESTION_TEMPLATES[t].format(situation=situation or "위에 적은 상황"))

    summary = {g: sum(1 for c in claims if c["grade"] == g) for g in GRADES}
    action = "공고 원문을 열어 접수기간과 신청자격을 직접 확인하기" if claims else "감리할 문장이 없어요. AI 답변을 그대로 붙여 넣어 주세요"
    return {
        "engine": ENGINE,
        "checked_at": datetime.now(KST).isoformat(timespec="seconds"),
        "situation": situation or "",
        "claims": claims,
        "questions": questions,
        "action": action,
        "summary": summary,
    }


def summary_line(result: dict) -> str:
    s = result["summary"]
    n = len(result["claims"])
    return f"주장 {n}개 — ✅{s['확인됨']} ❌{s['틀림']} ⚠️{s['말하지 않은 조건']} ❓{s['확인 불가']}"
