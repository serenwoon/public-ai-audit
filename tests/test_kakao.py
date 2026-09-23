"""순수 함수 시험. 소켓을 막고 돈다 — 이 시험이 네트워크를 쓰면 실패해야 한다."""
import json
import random
import socket
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spike"))
import kakao  # noqa: E402


class _NoNetwork(unittest.TestCase):
    def setUp(self):
        self._orig = socket.socket

        def _blocked(*a, **k):
            raise AssertionError("네트워크 사용 금지 — 순수 함수 시험이다")

        socket.socket = _blocked

    def tearDown(self):
        socket.socket = self._orig


class TestParseRequest(_NoNetwork):
    def test_full_payload(self):
        payload = {
            "userRequest": {"utterance": "  지연 30  ", "callbackUrl": "https://cb.example/x",
                            "user": {"id": "u1"}, "lang": "ko"},
            "bot": {"id": "b1"}, "intent": {"name": "폴백 블록"},
        }
        r = kakao.parse_request(payload)
        self.assertEqual(r["utterance"], "지연 30")
        self.assertEqual(r["callback_url"], "https://cb.example/x")
        self.assertEqual(r["user_id"], "u1")
        self.assertEqual(r["bot_id"], "b1")
        self.assertEqual(r["intent_name"], "폴백 블록")

    def test_missing_everything(self):
        r = kakao.parse_request({})
        self.assertEqual(r["utterance"], "")
        self.assertIsNone(r["callback_url"])
        self.assertIsNone(r["user_id"])

    def test_null_nested(self):
        r = kakao.parse_request({"userRequest": None, "bot": None})
        self.assertEqual(r["utterance"], "")


class TestParseDelay(_NoNetwork):
    def test_korean(self):
        self.assertEqual(kakao.parse_delay("지연 30"), 30)
        self.assertEqual(kakao.parse_delay("지연30"), 30)

    def test_english_case(self):
        self.assertEqual(kakao.parse_delay("DELAY 45"), 45)

    def test_cap(self):
        self.assertEqual(kakao.parse_delay("지연 999"), kakao.MAX_DELAY)

    def test_none(self):
        self.assertIsNone(kakao.parse_delay("청년수당 신청할 수 있나요?"))
        self.assertIsNone(kakao.parse_delay(""))
        self.assertIsNone(kakao.parse_delay(None))


class TestResponses(_NoNetwork):
    def test_simple_text_shape(self):
        r = kakao.simple_text("안녕")
        self.assertEqual(r["version"], "2.0")
        self.assertEqual(r["template"]["outputs"][0]["simpleText"]["text"], "안녕")
        json.dumps(r, ensure_ascii=False)  # 직렬화 가능

    def test_callback_wait_has_no_template(self):
        r = kakao.callback_wait("잠시만요")
        self.assertTrue(r["useCallback"])
        self.assertEqual(r["data"]["text"], "잠시만요")
        self.assertNotIn("template", r)  # 가이드: template 필드를 넣지 않는다
        self.assertIn("context", r)

    def test_echo_truncates(self):
        long = "가" * 500
        t = kakao.echo_text(long, limit=100)
        self.assertTrue(t.startswith("받았어요 (500자)"))
        self.assertTrue(t.endswith("…"))
        self.assertLess(len(t), 200)


if __name__ == "__main__":
    unittest.main()


class TestAuditOutputs(_NoNetwork):
    def _result(self, n=2, questions=("q1", "q2")):
        return {"summary": {"확인됨": 0, "틀림": 0, "말하지 않은 조건": 0, "확인 불가": n},
                "claims": [{"mark": "❓", "type": "마감", "text": f"주장 {i}", "grade": "확인 불가"} for i in range(n)],
                "questions": list(questions), "action": "공고 원문 열기"}

    def test_three_outputs_max(self):
        r = kakao.audit_outputs(self._result(), "https://x.vercel.app")
        outs = r["template"]["outputs"]
        self.assertEqual(len(outs), kakao.MAX_OUTPUTS)
        self.assertIn("주장 2개", outs[0]["simpleText"]["text"])
        self.assertIn("1. q1", outs[1]["simpleText"]["text"])
        card = outs[2]["basicCard"]
        self.assertEqual(card["buttons"][0]["webLinkUrl"], "https://x.vercel.app/")

    def test_no_base_url_no_button(self):
        card = kakao.audit_outputs(self._result())["template"]["outputs"][2]["basicCard"]
        self.assertNotIn("buttons", card)

    def test_many_claims_clipped(self):
        r = kakao.audit_outputs(self._result(n=12))
        t = r["template"]["outputs"][0]["simpleText"]["text"]
        self.assertIn("외 4개는 웹에서", t)
        self.assertLessEqual(len(t), 1000)


class TestResultLinkButton(_NoNetwork):
    """「웹에서 자세히」가 첫 화면이 아니라 이 답변의 감리 결과를 연다 (2026-09-23)."""

    def _result(self):
        return {"summary": {"확인됨": 0, "틀림": 0, "말하지 않은 조건": 1, "확인 불가": 0},
                "claims": [{"mark": "⚠️", "type": "마감", "text": "이번 달 말까지 신청하세요.", "grade": "말하지 않은 조건"}],
                "questions": ["q1"], "action": "공고 원문 열기", "basis_date": "2026-09-23"}

    def test_button_opens_this_answers_result_on_the_same_day(self):
        card = kakao.audit_outputs(self._result(), "https://x.vercel.app", text="이번 달 말까지 신청하세요.")["template"]["outputs"][2]["basicCard"]
        url = card["buttons"][0]["webLinkUrl"]
        self.assertTrue(url.startswith("https://x.vercel.app/#"))
        self.assertIn("d=2026-09-23", url)
        self.assertIn("a=", url)

    def test_too_long_answer_falls_back_to_home_and_says_so(self):
        rnd = random.Random(7)
        noisy = "".join(chr(rnd.randint(0xAC00, 0xD7A3)) for _ in range(3000))
        card = kakao.audit_outputs(self._result(), "https://x.vercel.app", text=noisy)["template"]["outputs"][2]["basicCard"]
        self.assertEqual(card["buttons"][0]["webLinkUrl"], "https://x.vercel.app/")
        self.assertIn("링크에 담지 못했어요", card["description"])


class TestDecodeJson(_NoNetwork):
    def test_ok(self):
        obj, err = kakao.decode_json('{"text":"청년수당"}'.encode("utf-8"))
        self.assertIsNone(err)
        self.assertEqual(obj["text"], "청년수당")

    def test_empty(self):
        self.assertEqual(kakao.decode_json(b""), ({}, None))

    def test_cp949_bytes(self):
        # 배포 후 git-bash curl 이 한글을 cp949로 보내 500이 났던 경우 (2026-09-23)
        obj, err = kakao.decode_json('{"text":"청년수당"}'.encode("cp949"))
        self.assertIsNone(obj)
        self.assertIn("UTF-8", err)

    def test_broken_json(self):
        obj, err = kakao.decode_json(b"{not json")
        self.assertIsNone(obj)
        self.assertIn("JSON", err)

    def test_non_object(self):
        obj, err = kakao.decode_json(b"[1,2]")
        self.assertIsNone(obj)
        self.assertIn("객체", err)
