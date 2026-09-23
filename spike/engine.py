"""감리 엔진 — 규칙(0.2). 순수 함수, 네트워크 없음.

「주장 분해 + 유형 분류 + 규칙 판정 + 되물을 질문」을 한다. 지금 규칙은 시간 규칙 하나다.
규칙이 판정하지 않은 주장은 원문 대조 전이므로 「확인 불가」로 남는다.
원문 대조 규칙(복지서비스 API)이 들어와도 audit()의 계약(반환 JSON 모양)은 유지하고 RULES에 더한다.
계약은 볼트 30_projects/공공AI_감리/10_기획/01_감리_판정규칙_초안 을 따른다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import time_rule

ENGINE = "rules-0.2"
KST = timezone(timedelta(hours=9), "KST")  # 확인일은 한국 시간 — 서버(Vercel)는 UTC다
GRADES = ("확인됨", "틀림", "말하지 않은 조건", "확인 불가")
GRADE_MARK = {"확인됨": "✅", "틀림": "❌", "말하지 않은 조건": "⚠️", "확인 불가": "❓"}
GRADE_RANK = {"틀림": 3, "말하지 않은 조건": 2, "확인됨": 1, "확인 불가": 0}  # 판정이 여럿이면 센 것

# 규칙 계약: rule(문장, 오늘) → {"grade","reason","expr","question"} 또는 None. 동점이면 앞선 규칙
RULES = (("time", time_rule.judge),)

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


def audit(text: str, situation: str = "", today: date | None = None) -> dict:
    """규칙 감리. 규칙이 판정하지 않은 주장은 「확인 불가」(원문 미확보)로 남는다."""
    today = today or datetime.now(KST).date()
    claims: list[dict] = []
    rule_questions: list[str] = []
    covered: set[str] = set()
    for i, s in enumerate(split_claims(text), 1):
        claim = {
            "id": i,
            "type": classify(s),
            "text": s,
            "grade": "확인 불가",
            "mark": GRADE_MARK["확인 불가"],
            "reason": "원문 미확보 — 대조할 공고·법령을 아직 받지 않았다",
            "source": None,
            "rule": None,
            "expr": None,
        }
        best = strongest([{**v, "rule": name} for name, rule in RULES if (v := rule(s, today))])
        if best:
            claim.update(grade=best["grade"], mark=GRADE_MARK[best["grade"]], reason=best["reason"],
                         rule=best["rule"], expr=best.get("expr"))
            q = best.get("question")
            if q and q not in rule_questions:
                rule_questions.append(q)
                covered.add(claim["type"])
        claims.append(claim)

    # 되물을 질문 — 규칙이 만든 구체 질문이 먼저, 그다음 유형별 기본 질문(이미 다룬 유형은 건너뛴다). 최대 셋
    questions = rule_questions[:3]
    for t in ("마감", "자격", "금액", "절차", "기관", "기타"):
        if len(questions) >= 3:
            break
        if t not in covered and any(c["type"] == t for c in claims):
            questions.append(_QUESTION_TEMPLATES[t].format(situation=situation or "위에 적은 상황"))

    summary = {g: sum(1 for c in claims if c["grade"] == g) for g in GRADES}
    action = "공고 원문을 열어 접수기간과 신청자격을 직접 확인하기" if claims else "감리할 문장이 없어요. AI 답변을 그대로 붙여 넣어 주세요"
    return {
        "engine": ENGINE,
        "checked_at": datetime.now(KST).isoformat(timespec="seconds"),
        "basis_date": today.isoformat(),  # 규칙이 쓴 날짜 — 결과 링크가 같은 날 기준으로 다시 계산한다
        "situation": situation or "",
        "claims": claims,
        "questions": questions,
        "action": action,
        "summary": summary,
    }


def strongest(verdicts: list) -> dict | None:
    """판정 여럿 중 가장 센 것(❌ > ⚠️ > ✅ > ❓). 동점이면 앞선 것."""
    vs = [v for v in verdicts if v]
    return max(vs, key=lambda v: GRADE_RANK[v["grade"]]) if vs else None


def summary_line(result: dict) -> str:
    s = result["summary"]
    n = len(result["claims"])
    return f"주장 {n}개 — ✅{s['확인됨']} ❌{s['틀림']} ⚠️{s['말하지 않은 조건']} ❓{s['확인 불가']}"
