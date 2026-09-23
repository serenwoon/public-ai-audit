"""Vercel 함수 — POST /api/skill  카카오 i 오픈빌더 스킬 (동기 경로만).

Vercel 서버리스에서는 응답을 보낸 뒤의 작업(콜백 POST)이 보장되지 않는다. 그래서 여기서는
5초 안에 끝나는 동기 경로만 둔다 — 스텁 엔진은 즉시 끝난다.
콜백 실측(「지연 N」)은 spike/server.py 를 로컬 + 터널로 띄워서 한다.
진짜 엔진(LLM + 원문 대조)이 5초를 넘기면 이 함수의 자리를 다시 정한다 — README 「호스팅 갈림길」.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "spike"))
import engine  # noqa: E402
import kakao  # noqa: E402


class handler(BaseHTTPRequestHandler):  # noqa: N801 — Vercel 규약
    def _json(self, status, obj):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _base_url(self):
        host = self.headers.get("x-forwarded-host") or self.headers.get("host") or ""
        proto = self.headers.get("x-forwarded-proto") or "https"
        return f"{proto}://{host}" if host else None

    def do_GET(self):  # noqa: N802
        self._json(200, {"ok": True, "what": "kakao skill endpoint — POST only", "engine": engine.ENGINE})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        payload, err = kakao.decode_json(self.rfile.read(length) if length else b"")
        if err:
            self._json(200, kakao.simple_text("메시지를 읽지 못했어요. 한 번 더 보내 주세요."))
            return
        req = kakao.parse_request(payload)
        # Vercel 로그로 원문 확인 (파일 로그는 못 쓴다)
        print(json.dumps({"skill_request": payload}, ensure_ascii=False)[:4000], flush=True)

        utterance = req["utterance"]
        if not utterance:
            self._json(200, kakao.simple_text("AI가 준 답을 그대로 붙여 넣거나 이 채팅으로 전달해 주세요."))
            return
        if kakao.parse_delay(utterance) is not None:
            self._json(200, kakao.simple_text("콜백 실측(지연 N)은 Vercel이 아니라 로컬 서버(spike/server.py)에서 합니다."))
            return
        result = engine.audit(utterance)
        self._json(200, kakao.audit_outputs(result, self._base_url(), text=utterance))

    def log_message(self, fmt, *args):
        return
