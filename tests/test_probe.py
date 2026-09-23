"""탐침 스크립트의 순수 함수 시험 — 키를 다루는 부분. 소켓을 막는다.

키는 가짜다. data.go.kr 키는 「인코딩」판(%2B, %3D …)과 「디코딩」판 두 가지로 주어지고,
인코딩판을 그대로 urlencode 하면 두 번 인코딩돼 SERVICE_KEY_IS_NOT_REGISTERED 가 난다.
"""
import socket
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import probe_welfare as probe  # noqa: E402

RAW_KEY = "Ab+cd/EF=="                 # 디코딩판 (가짜)
ENCODED_KEY = "Ab%2Bcd%2FEF%3D%3D"     # 같은 키의 인코딩판


class _NoNetwork(unittest.TestCase):
    def setUp(self):
        self._orig = socket.socket
        socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError("네트워크 금지"))

    def tearDown(self):
        socket.socket = self._orig


class TestNormalizeKey(_NoNetwork):
    def test_encoded_key_is_decoded_once(self):
        self.assertEqual(probe.normalize_key(ENCODED_KEY), RAW_KEY)

    def test_decoded_key_is_kept(self):
        self.assertEqual(probe.normalize_key(RAW_KEY), RAW_KEY)

    def test_whitespace_and_empty(self):
        self.assertEqual(probe.normalize_key("  " + RAW_KEY + "\n"), RAW_KEY)
        self.assertEqual(probe.normalize_key(None), "")
        self.assertEqual(probe.normalize_key(""), "")


class TestBuildUrl(_NoNetwork):
    def test_key_is_encoded_exactly_once(self):
        url = probe.build_url("NationalWelfarelistV001", {"callTp": "L", "searchWrd": "기초연금"}, RAW_KEY)
        parts = urlsplit(url)
        self.assertEqual(parts.netloc, "apis.data.go.kr")
        self.assertTrue(parts.path.endswith("/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"))
        q = parse_qs(parts.query)
        self.assertEqual(q["serviceKey"], [RAW_KEY])      # 한 번 풀면 원래 키 — 두 번 인코딩되지 않았다
        self.assertEqual(q["searchWrd"], ["기초연금"])
        self.assertNotIn("%25", url)                       # %가 다시 인코딩된 흔적(%25)이 없다


class TestRedact(_NoNetwork):
    def test_every_form_of_the_key_is_hidden(self):
        url = probe.build_url("NationalWelfarelistV001", {"callTp": "L"}, RAW_KEY)
        text = f"GET {url}\nraw={RAW_KEY}\nencoded={ENCODED_KEY}"
        out = probe.redact(text, RAW_KEY)
        self.assertNotIn(RAW_KEY, out)
        self.assertNotIn(ENCODED_KEY, out)
        self.assertNotIn("Ab%2Bcd", out)
        self.assertIn("***", out)

    def test_no_key_leaves_text(self):
        self.assertEqual(probe.redact("hello", ""), "hello")


class TestFirstServId(_NoNetwork):
    def test_finds_first_id(self):
        xml = "<wantedList><servList><servId> WLF00001188 </servId><servNm>기초연금</servNm></servList><servList><servId>WLF2</servId></servList></wantedList>"
        self.assertEqual(probe.first_serv_id(xml), "WLF00001188")

    def test_none_when_absent(self):
        self.assertIsNone(probe.first_serv_id("<OpenAPI_ServiceResponse><returnAuthMsg>SERVICE ERROR</returnAuthMsg></OpenAPI_ServiceResponse>"))


if __name__ == "__main__":
    unittest.main()
