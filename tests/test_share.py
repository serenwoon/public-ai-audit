"""결과 링크 시험 — 서버에 아무것도 저장하지 않고 링크의 # 뒤에 답변을 싣는다.

형식 계약(share.js 가 읽는 것):  #v=1&d=YYYY-MM-DD&a=<base64url(zlib(답변))>[&s=<base64url(zlib(상황))>]
# 뒤는 서버로 가지 않는다 — 답변이 우리 로그에도 Vercel에도 남지 않는 이유다.
"""
import base64
import json
import random
import shutil
import socket
import subprocess
import sys
import unittest
import zlib
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "spike"))
import share_link  # noqa: E402

BASE = "https://public-ai-audit.vercel.app"
TEXT = "이번 달 말까지 온라인으로 신청하세요. 월 50만원을 6개월 지원합니다."


def _unpack(v: str) -> str:
    """시험 쪽 디코더 — 제품 코드를 쓰지 않고 형식 계약만으로 푼다."""
    return zlib.decompress(base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))).decode("utf-8")


def _split(link: str):
    parts = urlsplit(link)
    return parts, {k: v[0] for k, v in parse_qs(parts.fragment).items()}


def _noisy_korean(n: int) -> str:
    """압축이 거의 안 되는 한글 — 길이 상한 시험용."""
    rnd = random.Random(7)
    return "".join(chr(rnd.randint(0xAC00, 0xD7A3)) for _ in range(n))


class _NoNetwork(unittest.TestCase):
    def setUp(self):
        self._orig = socket.socket
        socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("네트워크 금지"))

    def tearDown(self):
        socket.socket = self._orig


class TestResultLink(_NoNetwork):
    def test_link_carries_answer_and_day_after_hash(self):
        parts, q = _split(share_link.result_link(BASE, TEXT, day=date(2026, 9, 23)))
        self.assertEqual((parts.scheme, parts.netloc, parts.path), ("https", "public-ai-audit.vercel.app", "/"))
        self.assertEqual(parts.query, "")  # 답변이 쿼리(서버로 가는 부분)에 들어가면 안 된다
        self.assertEqual(q["v"], "1")
        self.assertEqual(q["d"], "2026-09-23")
        self.assertEqual(_unpack(q["a"]), TEXT)
        self.assertNotIn("s", q)

    def test_situation_is_carried_when_given(self):
        _, q = _split(share_link.result_link(BASE, TEXT, situation="서울 27세", day=date(2026, 9, 23)))
        self.assertEqual(_unpack(q["s"]), "서울 27세")

    def test_no_day_means_no_d(self):
        _, q = _split(share_link.result_link(BASE, TEXT))
        self.assertNotIn("d", q)

    def test_trailing_slash_in_base_is_not_doubled(self):
        self.assertTrue(share_link.result_link(BASE + "/", TEXT).startswith(BASE + "/#"))

    def test_too_long_answer_gives_no_link(self):
        self.assertIsNone(share_link.result_link(BASE, _noisy_korean(3000)))

    def test_custom_limit_is_respected(self):
        self.assertIsNone(share_link.result_link(BASE, TEXT, limit=60))


class TestParseDay(_NoNetwork):
    def test_valid_iso_day(self):
        self.assertEqual(share_link.parse_day("2026-09-23"), date(2026, 9, 23))

    def test_invalid_values_are_rejected(self):
        for v in ("2026-13-01", "2026-9-23", "abc", "", None, 20260923):
            with self.subTest(v=v):
                self.assertIsNone(share_link.parse_day(v))


NODE = shutil.which("node")


@unittest.skipUnless(NODE, "node 없음 — 브라우저 쪽 계약 시험을 건너뛴다")
class TestBrowserContract(unittest.TestCase):
    """share.js(브라우저) ↔ share_link.py(서버)가 같은 형식을 쓰는지 — node 로 share.js 를 그대로 돌린다."""

    def _node(self, payload: dict):
        r = subprocess.run([NODE, str(ROOT / "tests" / "share_node.js")],
                           input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           capture_output=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        return json.loads(r.stdout.decode("utf-8"))

    def test_browser_decodes_server_link(self):
        link = share_link.result_link(BASE, TEXT, situation="서울 27세", day=date(2026, 9, 23))
        out = self._node({"op": "decode", "hash": "#" + urlsplit(link).fragment})
        self.assertEqual(out, {"text": TEXT, "situation": "서울 27세", "day": "2026-09-23"})

    def test_server_reads_browser_link(self):
        out = self._node({"op": "encode", "text": TEXT, "situation": "", "day": "2026-09-23"})
        q = {k: v[0] for k, v in parse_qs(out["fragment"]).items()}
        self.assertEqual((_unpack(q["a"]), q["d"], q["v"]), (TEXT, "2026-09-23", "1"))
        self.assertNotIn("s", q)

    def test_browser_returns_null_for_garbage(self):
        self.assertIsNone(self._node({"op": "decode", "hash": "#v=1&a=@@not-base64@@"}))
        self.assertIsNone(self._node({"op": "decode", "hash": "#a=eJzLSM3JyQcABiwCFQ"}))  # v 없음


if __name__ == "__main__":
    unittest.main()
