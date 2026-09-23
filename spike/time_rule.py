"""시간 규칙 — 답변 속 시점 표현을 오늘(한국 시간)과 대조한다. 순수 함수, 네트워크 없음.

원문 없이는 틀렸다고 할 수 없으므로 ❌(틀림)는 만들지 않는다. 내리는 판정은 둘뿐이다.
  ⚠️ 말하지 않은 조건 — 이미 지난 마감 / 기준 시점이 없는 상대 날짜 / 지난 연도 기준 / 「현재 모집 중」
  ❓ 확인 불가      — 날짜는 분명하지만 원문과 대조 전 (이유만 구체화한다)
한 문장에 여럿이 있으면 위 순서대로 앞의 것 하나만 돌려준다.
규칙 계약: judge(문장, 오늘) → {"grade","reason","expr","question"} 또는 None
"""
from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

WARN = "말하지 않은 조건"
UNKNOWN = "확인 불가"

_FULL = re.compile(r"(\d{4})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})\s*일?")
_MD = re.compile(r"(?<!\d)(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DEADLINE_AFTER = re.compile(r"\s*까지")
_MONTH_END = re.compile(r"(이번\s*달|이달|금월)\s*(말일|말)")
_RELATIVE = re.compile(r"이번\s*달|이달|금월|다음\s*달|내달|이번\s*주|금주|다음\s*주|올해|금년|내년|작년|오늘|내일|모레")
_NOW = re.compile(r"(현재|지금)\s*.{0,12}?(모집|신청|접수|운영|진행)\s*(중|가능)?")
_YEAR_BASIS = re.compile(r"(\d{4})\s*년\s*(?:도\s*)?(기준|공고|예산|모집|회차|에는)")


def _fmt(d: date, with_year: bool = False) -> str:
    return f"{d.year}년 {d.month}월 {d.day}일" if with_year else f"{d.month}월 {d.day}일"


def _josa(word: str, with_final: str, without_final: str) -> str:
    """마지막 글자의 받침에 맞는 조사 — 「올해」가 / 「이번 달 말」이. 한글이 아니면 받침 있는 쪽."""
    last = word.strip()[-1:]
    if "가" <= last <= "힣":
        return with_final if (ord(last) - 0xAC00) % 28 else without_final
    return with_final


def _month_end(d: date) -> date:
    return date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:  # 9월 31일 같은 없는 날짜
        return None


def _absolute_dates(sentence: str, today: date) -> list[dict]:
    """문장 속 절대 날짜들 — 연도가 적혀 있는지, 「까지」가 붙은 마감인지와 함께."""
    found, taken = [], []
    for m in _FULL.finditer(sentence):
        taken.append(m.span())
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if d:
            found.append({"date": d, "with_year": True, "expr": m.group(0).strip(),
                          "deadline": bool(_DEADLINE_AFTER.match(sentence, m.end()))})
    for m in _MD.finditer(sentence):
        if any(a <= m.start() < b for a, b in taken):
            continue  # 「2026년 9월 15일」 안의 「9월 15일」을 두 번 세지 않는다
        d = _safe_date(today.year, int(m.group(1)), int(m.group(2)))
        if d:
            found.append({"date": d, "with_year": False, "expr": m.group(0).strip(),
                          "deadline": bool(_DEADLINE_AFTER.match(sentence, m.end()))})
    return found


def _relative_hint(expr: str, today: date) -> str | None:
    """상대 표현을 오늘 기준으로 풀어 쓴다. 풀 수 없으면 None."""
    e = re.sub(r"\s+", "", expr)
    if e in ("이번달", "이달", "금월"):
        return f"{today.month}월"
    if e in ("다음달", "내달"):
        return f"{today.month % 12 + 1}월"
    if e in ("올해", "금년"):
        return f"{today.year}년"
    if e == "내년":
        return f"{today.year + 1}년"
    if e == "작년":
        return f"{today.year - 1}년"
    if e == "오늘":
        return _fmt(today)
    if e == "내일":
        return _fmt(today + timedelta(days=1))
    if e == "모레":
        return _fmt(today + timedelta(days=2))
    return None


def judge(sentence: str, today: date) -> dict | None:
    dates = _absolute_dates(sentence, today)

    # 1) 이미 지난 마감
    for x in dates:
        if x["deadline"] and x["date"] < today:
            days = (today - x["date"]).days
            if x["with_year"]:
                reason = f"답변이 말한 마감({_fmt(x['date'], True)})이 이미 {days}일 지났다 — 새 회차가 있는지 확인해야 한다"
            else:
                reason = f"연도 없이 적힌 마감({_fmt(x['date'])})이 올해 기준으로 이미 {days}일 지났다 — 새 회차가 있는지 확인해야 한다"
            return {"grade": WARN, "reason": reason, "expr": x["expr"],
                    "question": f"답변에 적힌 마감 「{x['expr']}」이 이미 지났는데, 지금 신청할 수 있는 새 회차가 있는지 알려주세요."}

    # 2) 기준 시점이 없는 상대 날짜 — 「이번 달 말」은 말일까지 풀어 준다
    m = _MONTH_END.search(sentence)
    if m:
        expr = m.group(0)
        return {"grade": WARN,
                "reason": f"기준 시점이 없는 상대 날짜 「{expr}」 — 오늘({_fmt(today)}) 기준이면 {_fmt(_month_end(today))}이지만, 답변이 나온 날 기준이면 다를 수 있다",
                "expr": expr,
                "question": f"답변의 「{expr}」{_josa(expr, '이', '가')} 정확히 몇 월 며칠인지, 이번 회차 접수기간을 날짜로 알려주세요."}
    m = _RELATIVE.search(sentence)
    if m:
        expr, hint = m.group(0), _relative_hint(m.group(0), today)
        tail = f"오늘 기준이면 {hint}이지만, 답변이 나온 날 기준이면 다를 수 있다" if hint else "답변이 나온 날을 알 수 없다"
        return {"grade": WARN, "reason": f"기준 시점이 없는 상대 날짜 「{expr}」 — {tail}", "expr": expr,
                "question": f"답변의 「{expr}」{_josa(expr, '이', '가')} 정확히 언제인지 날짜로 알려주세요."}

    # 3) 지난 연도 기준
    for m in _YEAR_BASIS.finditer(sentence):
        y = int(m.group(1))
        if y < today.year:
            expr = m.group(0)
            return {"grade": WARN, "reason": f"지난 연도({y}년) 기준 — {today.year}년 현행 값과 다를 수 있다", "expr": expr,
                    "question": f"답변의 「{expr}」 내용이 올해({today.year}년)에도 같은지, 현행 공고 기준으로 알려주세요."}

    # 4) 「현재 모집 중」 — 모집·신청 맥락이 있을 때만 (「현재 거주지」는 시점 주장이 아니다)
    m = _NOW.search(sentence)
    if m:
        expr = m.group(0).strip()
        return {"grade": WARN, "reason": f"「{expr}」의 기준 시점이 없다 — 모집·신청 여부는 날짜로 확인해야 한다", "expr": expr,
                "question": f"「{expr}」{_josa(expr, '이라고', '라고')} 했는데, 모집·신청 기간을 날짜로 알려주세요."}

    # 5) 날짜는 분명하다 — 등급은 그대로 두고 이유만 구체화
    if dates:
        x = max(dates, key=lambda d: (d["deadline"], d["date"]))
        if x["deadline"]:
            detail = f"{_fmt(x['date'], x['with_year'])}까지, 오늘부터 {(x['date'] - today).days}일 남음"
        else:
            detail = _fmt(x["date"], x["with_year"])
        return {"grade": UNKNOWN, "reason": f"날짜는 분명하다({detail}) — 원문과 대조 전", "expr": x["expr"], "question": None}
    return None
