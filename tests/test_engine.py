"""스텁 엔진 계약 시험. 소켓을 막고 돈다."""
import json
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spike"))
import engine  # noqa: E402

SAMPLE = ("서울에 거주하는 만 19~34세 미취업 청년이면 청년수당을 신청하실 수 있습니다. "
          "월 50만원을 최대 6개월 지원합니다.\n이번 달 말까지 청년몽땅정보통에서 온라인으로 신청하시면 됩니다. "
          "자세한 내용은 주민센터에 문의하세요.")


class _NoNetwork(unittest.TestCase):
    def setUp(self):
        self._orig = socket.socket
        socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("네트워크 금지"))

    def tearDown(self):
        socket.socket = self._orig


class TestSplitAndClassify(_NoNetwork):
    def test_split(self):
        parts = engine.split_claims(SAMPLE)
        self.assertEqual(len(parts), 4)

    def test_classify_each_type(self):
        self.assertEqual(engine.classify("이번 달 말까지 신청 가능합니다"), "마감")
        self.assertEqual(engine.classify("월 50만원을 지원합니다"), "금액")
        self.assertEqual(engine.classify("만 19~34세 미취업자가 대상입니다"), "자격")
        self.assertEqual(engine.classify("온라인으로 신청하시면 됩니다"), "절차")
        self.assertEqual(engine.classify("주민센터에 문의하세요"), "기관")
        self.assertEqual(engine.classify("좋은 하루 보내세요"), "기타")

    def test_short_fragments_dropped(self):
        self.assertEqual(engine.split_claims("네. 감사합니다."), [])


class TestAuditContract(_NoNetwork):
    def test_shape(self):
        r = engine.audit(SAMPLE, situation="서울 27세 미취업")
        self.assertEqual(r["engine"], engine.ENGINE)
        self.assertEqual(len(r["claims"]), 4)
        for c in r["claims"]:
            self.assertIn(c["grade"], engine.GRADES)
            self.assertEqual(c["grade"], "확인 불가")  # 스텁은 전부 확인 불가
            self.assertEqual(c["mark"], "❓")
            self.assertIn(c["type"], ("자격", "마감", "금액", "절차", "기관", "기타"))
        self.assertLessEqual(len(r["questions"]), 3)
        self.assertGreaterEqual(len(r["questions"]), 1)
        self.assertIn("서울 27세 미취업", " ".join(r["questions"]))  # 상황이 질문에 들어간다
        self.assertTrue(r["action"])
        self.assertEqual(sum(r["summary"].values()), 4)
        json.dumps(r, ensure_ascii=False)

    def test_question_priority_deadline_first(self):
        r = engine.audit(SAMPLE)
        self.assertIn("접수기간", r["questions"][0])

    def test_empty(self):
        r = engine.audit("")
        self.assertEqual(r["claims"], [])
        self.assertEqual(r["questions"], [])
        self.assertIn("감리할 문장이 없어요", r["action"])

    def test_checked_at_is_kst(self):
        # 배포 후 확인일이 UTC(+00:00)로 찍혔다 (2026-09-23). 확인일은 근거라 한국 시간으로 고정한다
        self.assertTrue(engine.audit(SAMPLE)["checked_at"].endswith("+09:00"))

    def test_summary_line(self):
        r = engine.audit(SAMPLE)
        self.assertTrue(engine.summary_line(r).startswith("주장 4개"))


if __name__ == "__main__":
    unittest.main()
