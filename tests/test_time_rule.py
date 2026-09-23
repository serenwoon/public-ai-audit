"""시간 규칙 시험 — 오늘 날짜를 2026-09-23으로 고정해 돈다. 소켓을 막는다.

기대값은 전부 손으로 셈했다: 9/23 기준 9/15는 8일 전, 9월 말일은 30일, 2027년 2월 말일은 28일.
"""
import socket
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spike"))
import time_rule  # noqa: E402

TODAY = date(2026, 9, 23)
WARN = "말하지 않은 조건"
UNKNOWN = "확인 불가"


class _NoNetwork(unittest.TestCase):
    def setUp(self):
        self._orig = socket.socket
        socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("네트워크 금지"))

    def tearDown(self):
        socket.socket = self._orig


class TestRelative(_NoNetwork):
    def test_month_end_is_resolved_against_today(self):
        v = time_rule.judge("이번 달 말까지 온라인으로 신청하세요.", TODAY)
        self.assertEqual(v["grade"], WARN)
        self.assertIn("9월 30일", v["reason"])
        self.assertIn("이번 달 말", v["question"])

    def test_month_end_in_february_non_leap_year(self):
        v = time_rule.judge("이달 말까지 서류를 내야 합니다.", date(2027, 2, 10))
        self.assertIn("2월 28일", v["reason"])

    def test_next_month_in_december_wraps_to_january(self):
        v = time_rule.judge("다음 달부터 신청을 받습니다.", date(2026, 12, 5))
        self.assertIn("1월", v["reason"])
        self.assertNotIn("13월", v["reason"])

    def test_current_recruiting_has_no_anchor(self):
        v = time_rule.judge("현재 모집 중입니다.", TODAY)
        self.assertEqual(v["grade"], WARN)

    def test_current_without_recruiting_context_is_not_a_time_claim(self):
        self.assertIsNone(time_rule.judge("현재 거주지가 서울이어야 합니다.", TODAY))


class TestAbsolute(_NoNetwork):
    def test_passed_deadline_without_year_counts_days(self):
        v = time_rule.judge("9월 15일까지 신청하셔야 합니다.", TODAY)
        self.assertEqual(v["grade"], WARN)
        self.assertIn("8일", v["reason"])

    def test_passed_deadline_with_year_counts_days(self):
        v = time_rule.judge("2026년 9월 15일까지 접수합니다.", TODAY)
        self.assertEqual(v["grade"], WARN)
        self.assertIn("8일", v["reason"])

    def test_past_start_date_is_not_warned(self):
        v = time_rule.judge("2024년 1월 1일부터 시행된 제도입니다.", TODAY)
        self.assertTrue(v is None or v["grade"] == UNKNOWN)

    def test_future_deadline_refines_reason_but_stays_unknown(self):
        v = time_rule.judge("10월 1일부터 12월 31일까지 신청할 수 있습니다.", TODAY)
        self.assertEqual(v["grade"], UNKNOWN)
        self.assertIn("12월 31일", v["reason"])

    def test_deadline_today_has_not_passed(self):
        # 경계: 오늘 마감이면 오늘은 아직 낼 수 있다 (< 가 <= 로 바뀌면 잡힌다)
        v = time_rule.judge("9월 23일까지 신청하세요.", TODAY)
        self.assertEqual(v["grade"], UNKNOWN)
        self.assertIn("0일 남음", v["reason"])

    def test_invalid_calendar_date_does_not_crash_or_warn(self):
        v = time_rule.judge("9월 31일까지 신청하세요.", TODAY)
        self.assertTrue(v is None or v["grade"] != WARN)


class TestYearBasis(_NoNetwork):
    def test_stale_year_basis_names_both_years(self):
        v = time_rule.judge("2025년 기준으로 월 20만원을 지원합니다.", TODAY)
        self.assertEqual(v["grade"], WARN)
        self.assertIn("2025", v["reason"])
        self.assertIn("2026", v["reason"])

    def test_current_year_basis_is_not_warned(self):
        self.assertIsNone(time_rule.judge("2026년 기준으로 월 20만원을 지원합니다.", TODAY))


class TestNoTime(_NoNetwork):
    def test_sentence_without_time_expression(self):
        self.assertIsNone(time_rule.judge("만 65세 이상이면 받을 수 있습니다.", TODAY))

    def test_months_of_support_are_not_dates(self):
        self.assertIsNone(time_rule.judge("월 50만원을 최대 6개월 지원합니다.", TODAY))


class TestKoreanParticles(_NoNetwork):
    """질문은 그 AI에 그대로 붙여 넣는 문장이다. 받침에 맞는 조사가 붙어야 한다 (2026-09-23 발견: 「올해」이)."""

    def test_vowel_ending_expression_takes_ga(self):
        q = time_rule.judge("올해부터 지급액이 인상되었습니다.", TODAY)["question"]
        self.assertIn("「올해」가", q)

    def test_consonant_ending_expression_takes_i(self):
        q = time_rule.judge("이번 달 말까지 온라인으로 신청하세요.", TODAY)["question"]
        self.assertIn("「이번 달 말」이", q)

    def test_now_expression_particle_follows_last_syllable(self):
        q = time_rule.judge("지금 접수 중이니 서두르세요.", TODAY)["question"]
        self.assertIn("「지금 접수 중」이라고", q)
        q = time_rule.judge("지금 바로 접수하세요.", TODAY)["question"]
        self.assertIn("「지금 바로 접수」라고", q)


if __name__ == "__main__":
    unittest.main()
